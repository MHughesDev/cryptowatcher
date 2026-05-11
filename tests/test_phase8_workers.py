from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from wigs import workers


class _SessionContext:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeDB:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.executed = []

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def execute(self, stmt):
        self.executed.append(stmt)


def test_build_scheduler_registers_phase8_jobs():
    scheduler = workers.build_scheduler()
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert job_ids == {
        "refresh_candidates",
        "label_outcomes",
        "update_posteriors",
        "update_wallet_scores",
        "discover_new_wallets",
        "rebuild_clusters",
        "retrain_wallet_quality_weights",
        "run_backtest",
    }


@pytest.mark.asyncio
async def test_label_alert_outcomes_uses_dexscreener_liquidity(monkeypatch):
    db = _FakeDB()
    alert = SimpleNamespace(
        id="alert-1",
        token_mint="mint-1",
        sent_at=datetime.utcnow() - timedelta(days=8),
    )
    captured = {}

    monkeypatch.setattr(workers, "AsyncSessionLocal", lambda: _SessionContext(db))

    async def fake_unlabeled(_db):
        return [alert]

    async def fake_pairs(token_mint):
        assert token_mint == "mint-1"
        return [{"liquidity": {"usd": 12_500}}, {"liquidity": {"usd": 9_000}}]

    async def fake_label_token_outcome(**kwargs):
        captured.update(kwargs)
        return "SURVIVOR"

    monkeypatch.setattr(workers.alert_repo, "list_unlabeled_alerts", fake_unlabeled)
    monkeypatch.setattr(workers.dexscreener, "get_token_pairs", fake_pairs)
    monkeypatch.setattr(workers, "label_token_outcome", fake_label_token_outcome)

    await workers.label_alert_outcomes()

    assert captured["initial_liquidity_usd"] == 12_500.0
    assert captured["alert_id"] == "alert-1"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_refresh_tracked_wallet_set_scores_discovered_wallets(monkeypatch):
    db = _FakeDB()
    saved_scores = []
    upserted = []
    active_wallets = [SimpleNamespace(wallet_address="kol-1", wallet_type="KOL_PRECALL")]
    outcomes = [SimpleNamespace(token_mint="winner-1", label="HEAVY_HITTER")]
    events = [SimpleNamespace(token_mint="winner-1", amount_usd=150.0)]

    monkeypatch.setattr(workers, "AsyncSessionLocal", lambda: _SessionContext(db))

    async def fake_outcomes(_db, limit=200):
        return outcomes

    async def fake_wallets(_db):
        return active_wallets

    async def fake_build_seed_wallet_set(historical_winner_mints, kol_wallets, *_args):
        assert historical_winner_mints == ["winner-1"]
        assert kol_wallets == ["kol-1"]
        return ["new-wallet"]

    async def fake_recent_events(_db, wallet_address, limit=100):
        assert wallet_address == "new-wallet"
        return events

    async def fake_get_tracked_wallet(_db, wallet_address):
        assert wallet_address == "new-wallet"
        return None

    async def fake_upsert_tracked_wallet(_db, address, label=None, *, source="manual", wallet_type="UNKNOWN"):
        upserted.append((address, source, wallet_type))
        return SimpleNamespace(wallet_address=address, wallet_type=wallet_type, is_active=True)

    async def fake_save_wallet_score(_db, wallet_address, scores):
        saved_scores.append((wallet_address, scores["wallet_quality"]))
        return SimpleNamespace(wallet_address=wallet_address)

    monkeypatch.setattr(workers.alert_repo, "list_recent_completed_outcomes", fake_outcomes)
    monkeypatch.setattr(workers.wallet_repo, "list_active_wallets", fake_wallets)
    monkeypatch.setattr(workers.wallet_universe, "build_seed_wallet_set", fake_build_seed_wallet_set)
    monkeypatch.setattr(workers.wallet_repo, "get_recent_wallet_events", fake_recent_events)
    monkeypatch.setattr(workers.wallet_repo, "get_tracked_wallet", fake_get_tracked_wallet)
    monkeypatch.setattr(workers.wallet_repo, "upsert_tracked_wallet", fake_upsert_tracked_wallet)
    monkeypatch.setattr(workers.wallet_repo, "save_wallet_score", fake_save_wallet_score)

    await workers.refresh_tracked_wallet_set()

    assert upserted == [("new-wallet", "seed_builder", "SCOUT")]
    assert saved_scores
    assert saved_scores[0][0] == "new-wallet"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_update_wallet_scores_updates_wallet_lifecycle(monkeypatch):
    db = _FakeDB()
    now = datetime.utcnow()
    degraded_wallet = SimpleNamespace(
        wallet_address="w-degraded",
        lifecycle="ACTIVE",
        is_active=True,
    )
    strong_wallet = SimpleNamespace(
        wallet_address="w-strong",
        lifecycle="DISCOVERED",
        is_active=False,
    )
    wallets = [degraded_wallet, strong_wallet]

    monkeypatch.setattr(workers, "AsyncSessionLocal", lambda: _SessionContext(db))
    monkeypatch.setattr(workers.settings, "wallet_degraded_quality_threshold", 25)
    monkeypatch.setattr(workers.settings, "wallet_active_quality_threshold", 50)

    async def fake_wallets(_db):
        return wallets

    async def fake_events(_db, wallet_address, limit=100):
        return [
            SimpleNamespace(
                wallet_address=wallet_address,
                token_mint="mint-1",
                amount_usd=100.0 if wallet_address == "w-strong" else -10.0,
                event_time=now,
                event_type="BUY",
            )
        ]

    async def fake_cluster(_db, wallet_address):
        return None

    async def fake_save_wallet_score(_db, wallet_address, scores):
        return SimpleNamespace(wallet_address=wallet_address, wallet_quality=scores["wallet_quality"])

    def fake_score_wallet(wallet_address, trades, cluster_members, last_active_days_ago):
        del trades, cluster_members, last_active_days_ago
        quality = 20 if wallet_address == "w-degraded" else 70
        return {
            "wallet_quality": quality,
            "realized_pnl_score": quality,
            "early_entry_score": 50,
            "lead_lag_score": 50,
            "exit_quality_score": 50,
            "rug_avoidance_score": 50,
            "repeatability_score": 50,
            "independence_score": 50,
            "freshness_score": 50,
        }

    monkeypatch.setattr(workers.wallet_repo, "list_active_wallets", fake_wallets)
    monkeypatch.setattr(workers.wallet_repo, "get_recent_wallet_events", fake_events)
    monkeypatch.setattr(workers.graph_repo, "get_wallet_cluster", fake_cluster)
    monkeypatch.setattr(workers.wallet_repo, "save_wallet_score", fake_save_wallet_score)
    monkeypatch.setattr(workers.wallet_quality, "score_wallet", fake_score_wallet)

    await workers.update_wallet_scores()

    assert degraded_wallet.lifecycle == "RETIRED"
    assert degraded_wallet.is_active is False
    assert strong_wallet.lifecycle == "ACTIVE"
    assert strong_wallet.is_active is True
    assert db.commits == 1


@pytest.mark.asyncio
async def test_rebuild_wallet_clusters_clears_and_saves(monkeypatch):
    db = _FakeDB()
    saved_clusters = []
    wallets = [SimpleNamespace(wallet_address="w1", source="fund-a")]

    monkeypatch.setattr(workers, "AsyncSessionLocal", lambda: _SessionContext(db))

    async def fake_pairs(_db, min_shared_tokens=2):
        assert min_shared_tokens == 2
        return [("w1", "w2", 3)]

    async def fake_wallets(_db):
        return wallets

    async def fake_recent_events(_db, wallet_address, limit=200):
        return [
            SimpleNamespace(
                wallet_address=wallet_address,
                token_mint="mint-1",
                event_type="BUY",
                event_time=datetime.utcnow(),
            )
        ]

    def fake_build_clusters(copurchase_pairs, wallet_events, funding_sources):
        assert copurchase_pairs == [("w1", "w2", 3)]
        assert funding_sources == {"w1": "fund-a"}
        assert wallet_events[0]["wallet_address"] == "w1"
        return [{"cluster_type": "SMART_MONEY", "members": ["w1", "w2"], "suspicion_score": 80.0}]

    async def fake_save_cluster(_db, cluster_type, members, suspicion_score):
        saved_clusters.append((cluster_type, members, suspicion_score))
        return SimpleNamespace(id="cluster-1")

    monkeypatch.setattr(workers.graph_repo, "get_copurchase_pairs", fake_pairs)
    monkeypatch.setattr(workers.wallet_repo, "list_active_wallets", fake_wallets)
    monkeypatch.setattr(workers.wallet_repo, "get_recent_wallet_events", fake_recent_events)
    monkeypatch.setattr(workers.clustering, "build_clusters", fake_build_clusters)
    monkeypatch.setattr(workers.graph_repo, "save_cluster", fake_save_cluster)

    await workers.rebuild_wallet_clusters()

    assert len(db.executed) == 2
    assert saved_clusters == [("SMART_MONEY", ["w1", "w2"], 0.8)]
    assert db.commits == 1


@pytest.mark.asyncio
async def test_retrain_wallet_quality_weights_invokes_feedback(monkeypatch):
    db = _FakeDB()
    captured = {}

    monkeypatch.setattr(workers, "AsyncSessionLocal", lambda: _SessionContext(db))

    async def fake_retrain(_db):
        captured["called"] = True
        return {"pnl": 0.3, "early_entry": 0.7}

    monkeypatch.setattr(workers, "retrain_weights_algo", fake_retrain)

    await workers.retrain_wallet_quality_weights()

    assert captured["called"] is True


@pytest.mark.asyncio
async def test_run_backtest_logs_summary(monkeypatch):
    db = _FakeDB()
    messages = []
    outcomes = [
        SimpleNamespace(label="HEAVY_HITTER"),
        SimpleNamespace(label="TRADEABLE_RUNNER"),
        SimpleNamespace(label="RUG"),
    ]

    monkeypatch.setattr(workers, "AsyncSessionLocal", lambda: _SessionContext(db))

    async def fake_outcomes(_db, limit=500):
        return outcomes

    def fake_log(message, *args):
        messages.append(message % args)

    monkeypatch.setattr(workers.alert_repo, "list_recent_completed_outcomes", fake_outcomes)
    monkeypatch.setattr(workers.log, "info", fake_log)

    await workers.run_backtest()

    assert any("hit_rate=0.667" in message for message in messages)
