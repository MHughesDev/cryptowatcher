import asyncio
from types import SimpleNamespace

from wigs import app as app_module
from wigs import workers


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    async def body(self):
        return b"[]"

    async def json(self):
        return self._payload


class _FakeExecuteResult:
    def __init__(self, tracked):
        self._tracked = tracked

    def scalar_one_or_none(self):
        return self._tracked


class _FakeDB:
    def __init__(self, tracked=True):
        self.tracked = tracked

    async def execute(self, _stmt):
        return _FakeExecuteResult(SimpleNamespace(wallet_address="w1") if self.tracked else None)


def test_webhook_skips_untracked_wallet(monkeypatch):
    async def fake_handle_wallet_event(event, wallet_address, db):
        raise AssertionError("should not be called for untracked wallets")

    monkeypatch.setattr(app_module, "handle_wallet_event", fake_handle_wallet_event)

    request = _FakeRequest([{"feePayer": "w1", "accountData": []}])
    db = _FakeDB(tracked=False)

    response = asyncio.run(app_module.helius_webhook(request=request, db=db, x_helius_signature=None))
    assert response.status_code == 200
    assert b'"processed":0' in response.body


def test_webhook_processes_tracked_wallet(monkeypatch):
    calls = {"count": 0}

    async def fake_handle_wallet_event(event, wallet_address, db):
        calls["count"] += 1
        return {"ok": True}

    monkeypatch.setattr(app_module, "handle_wallet_event", fake_handle_wallet_event)

    request = _FakeRequest([{"feePayer": "w1", "accountData": []}])
    db = _FakeDB(tracked=True)

    response = asyncio.run(app_module.helius_webhook(request=request, db=db, x_helius_signature=None))
    assert response.status_code == 200
    assert b'"processed":1' in response.body
    assert calls["count"] == 1


class _SessionContext:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _WorkerDB:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


def test_update_wallet_scores_threshold_boundaries(monkeypatch):
    db = _WorkerDB()
    wallets = [
        SimpleNamespace(wallet_address="w24", lifecycle="ACTIVE", is_active=True),
        SimpleNamespace(wallet_address="w25", lifecycle="ACTIVE", is_active=True),
        SimpleNamespace(wallet_address="w49", lifecycle="ACTIVE", is_active=True),
        SimpleNamespace(wallet_address="w50", lifecycle="ACTIVE", is_active=True),
    ]
    score_map = {"w24": 24, "w25": 25, "w49": 49, "w50": 50}

    monkeypatch.setattr(workers, "AsyncSessionLocal", lambda: _SessionContext(db))
    monkeypatch.setattr(workers.settings, "wallet_degraded_quality_threshold", 25)
    monkeypatch.setattr(workers.settings, "wallet_active_quality_threshold", 50)

    async def fake_wallets(_db):
        return wallets

    async def fake_events(_db, wallet_address, limit=100):
        return [SimpleNamespace(wallet_address=wallet_address, token_mint="mint-1", amount_usd=100.0, event_time=workers.datetime.utcnow())]

    async def fake_cluster(_db, wallet_address):
        return None

    async def fake_save_wallet_score(_db, wallet_address, scores):
        return SimpleNamespace(wallet_address=wallet_address, wallet_quality=scores["wallet_quality"])

    def fake_score_wallet(wallet_address, trades, cluster_members, last_active_days_ago):
        quality = score_map[wallet_address]
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

    asyncio.run(workers.update_wallet_scores())

    assert wallets[0].lifecycle == "RETIRED" and wallets[0].is_active is False
    assert wallets[1].lifecycle == "DEGRADED" and wallets[1].is_active is True
    assert wallets[2].lifecycle == "DEGRADED" and wallets[2].is_active is True
    assert wallets[3].lifecycle == "ACTIVE" and wallets[3].is_active is True
    assert db.commits == 1
