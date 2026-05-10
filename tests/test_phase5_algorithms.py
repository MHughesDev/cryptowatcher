from datetime import datetime
from types import SimpleNamespace

import pytest

from wigs.algorithms.execution_verifier import score_execution
from wigs.algorithms.feedback import retrain_wallet_quality_weights, update_all_wallet_scores_from_recent_outcomes
from wigs.algorithms.history_analyzer import analyze, score_early_holder_quality
from wigs.algorithms.market_verifier import MarketContext, check_volume_authenticity, fetch_market_context, score_market_context
from wigs.algorithms.outcome_labeler import label_token_outcome
from wigs.clients.jupiter import SellabilityReport


def test_check_volume_authenticity_reasonable_ratio():
    score = check_volume_authenticity(volume_5m=10_000, buyers_5m=20, avg_trade_size_usd=500)
    assert 0 <= score <= 1
    assert score > 0


def test_score_market_context_combines_inputs():
    ctx = MarketContext(
        liquidity_usd=100_000,
        price_usd=0.01,
        market_cap=1_000_000,
        fdv=1_500_000,
        volume_5m=20_000,
        volume_1h=50_000,
        volume_24h=100_000,
        buyers_5m=25,
        sellers_5m=10,
        unique_buyers_5m=25,
        avg_trade_size_usd=800,
        pool_age_minutes=90,
        primary_pool_address="pool1",
        source="test",
    )
    score = score_market_context(ctx)
    assert 0 <= score <= 100
    assert score > 30


@pytest.mark.asyncio
async def test_fetch_market_context_prefers_best_available_sources(monkeypatch):
    async def fake_pairs(token_mint):
        return [{
            "liquidity": {"usd": 25_000},
            "priceUsd": "0.05",
            "volume": {"m5": 5_000, "h1": 10_000, "h24": 50_000},
            "txns": {"m5": {"buys": 10, "sells": 5}},
            "pairAddress": "pair1",
            "marketCap": "1000000",
            "fdv": "1200000",
        }]

    async def fake_pools(token_mint, network="solana"):
        return []

    async def fake_overview(token_mint):
        return {"liquidity": 30_000, "price": 0.06}

    monkeypatch.setattr("wigs.algorithms.market_verifier.dexscreener.get_token_pairs", fake_pairs)
    monkeypatch.setattr("wigs.algorithms.market_verifier.geckoterminal.get_token_pools", fake_pools)
    monkeypatch.setattr("wigs.algorithms.market_verifier.birdeye.get_token_overview", fake_overview)

    ctx = await fetch_market_context("mint1")
    assert ctx.liquidity_usd == 25_000
    assert ctx.primary_pool_address == "pair1"


def test_score_execution_thresholds():
    strong = score_execution(SellabilityReport(True, 0.01, 0.05, 0.10, True))
    weak = score_execution(SellabilityReport(True, 0.05, 0.25, 0.70, True))
    extreme = score_execution(SellabilityReport(True, 0.05, 0.40, 0.90, True))
    none = score_execution(SellabilityReport(False, None, None, None, False))
    assert strong == 100
    assert weak == 60
    assert extreme == 0
    assert none == 0


@pytest.mark.asyncio
async def test_score_early_holder_quality_averages_wallet_scores(monkeypatch):
    buyers = [SimpleNamespace(wallet_address="w1"), SimpleNamespace(wallet_address="w2")]

    async def fake_events(db, token_mint, event_type="BUY"):
        return buyers

    async def fake_score(db, address):
        return SimpleNamespace(wallet_quality=80 if address == "w1" else 60)

    monkeypatch.setattr("wigs.algorithms.history_analyzer.wallet_repo.get_wallet_events_for_token", fake_events)
    monkeypatch.setattr("wigs.algorithms.history_analyzer.wallet_repo.get_wallet_score", fake_score)

    score = await score_early_holder_quality("mint1", db=object())
    assert score == 70


@pytest.mark.asyncio
async def test_analyze_combines_history_components(monkeypatch):
    async def fake_creator(*args, **kwargs):
        return 80.0

    async def fake_early(*args, **kwargs):
        return 70.0

    async def fake_context(*args, **kwargs):
        return {"market": SimpleNamespace(liquidity_usd=10_000)}

    async def fake_orders(token_mint):
        return []

    async def fake_launch(*args, **kwargs):
        return 90.0

    monkeypatch.setattr("wigs.algorithms.history_analyzer.score_creator_reputation", fake_creator)
    monkeypatch.setattr("wigs.algorithms.history_analyzer.score_early_holder_quality", fake_early)
    monkeypatch.setattr("wigs.algorithms.history_analyzer.token_repo.get_latest_token_context", fake_context)
    monkeypatch.setattr("wigs.algorithms.history_analyzer.dexscreener.get_paid_orders", fake_orders)
    monkeypatch.setattr("wigs.algorithms.history_analyzer.score_launch_context", fake_launch)

    score = await analyze("mint1", "creator1", 10.0, object(), object(), object())
    assert score == 79


@pytest.mark.asyncio
async def test_label_token_outcome_saves_outcome(monkeypatch):
    saved = {}

    async def fake_measure_return(*args, **kwargs):
        return 1.4

    async def fake_measure_liq(*args, **kwargs):
        return 20_000.0

    async def fake_pairs(token_mint):
        return [{"fdv": 1000, "priceChange": {"h24": 80}}]

    async def fake_save_outcome(db, token_mint, alert_id, label, **kwargs):
        saved["label"] = label
        saved["token_mint"] = token_mint
        return SimpleNamespace(label=label)

    monkeypatch.setattr("wigs.algorithms.outcome_labeler.measure_tradable_return", fake_measure_return)
    monkeypatch.setattr("wigs.algorithms.outcome_labeler.measure_liquidity_at_time", fake_measure_liq)
    monkeypatch.setattr("wigs.algorithms.outcome_labeler.alert_repo.save_outcome", fake_save_outcome)

    label = await label_token_outcome(
        "mint1",
        "alert1",
        datetime.utcnow(),
        5_000.0,
        jupiter_client=SimpleNamespace(),
        dexscreener_client=SimpleNamespace(get_token_pairs=fake_pairs),
        db=object(),
    )

    assert label == saved["label"]
    assert saved["token_mint"] == "mint1"


@pytest.mark.asyncio
async def test_update_all_wallet_scores_from_recent_outcomes_updates_rows(monkeypatch):
    outcomes = [SimpleNamespace(token_mint="mint1", label="TRADEABLE_RUNNER")]
    events = [SimpleNamespace(wallet_address="w1")]
    saved = []

    async def fake_outcomes(db, limit=500):
        return outcomes

    async def fake_events(db, token_mint, event_type="BUY"):
        return events

    async def fake_get_posterior(db, address):
        return None

    async def fake_save(db, address, alpha, beta):
        saved.append((address, alpha, beta))
        return SimpleNamespace(wallet_address=address, alpha=alpha, beta=beta)

    monkeypatch.setattr("wigs.algorithms.feedback.alert_repo.list_recent_completed_outcomes", fake_outcomes)
    monkeypatch.setattr("wigs.algorithms.feedback.wallet_repo.get_wallet_events_for_token", fake_events)
    monkeypatch.setattr("wigs.algorithms.feedback.wallet_repo.get_wallet_beta_posterior", fake_get_posterior)
    monkeypatch.setattr("wigs.algorithms.feedback.wallet_repo.save_wallet_beta_posterior", fake_save)

    updated = await update_all_wallet_scores_from_recent_outcomes(object())
    assert updated == 1
    assert saved[0][0] == "w1"


@pytest.mark.asyncio
async def test_retrain_wallet_quality_weights_returns_weight_map():
    weights = await retrain_wallet_quality_weights(object())
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert "lead_lag" in weights
