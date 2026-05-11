"""Tests for Thompson Sampling feedback loop."""

import asyncio
from types import SimpleNamespace

from wigs.algorithms.feedback import (
    classify_outcome_from_returns,
    compute_posterior_update,
    sample_wallet_trust,
    update_all_wallet_scores_from_recent_outcomes,
)


def test_tradeable_runner_increments_alpha():
    update = compute_posterior_update("wallet_X", "TRADEABLE_RUNNER")
    assert update.alpha_delta == 1.0
    assert update.beta_delta == 0.0


def test_rug_increments_beta():
    update = compute_posterior_update("wallet_X", "RUG")
    assert update.alpha_delta == 0.0
    assert update.beta_delta == 1.0


def test_survivor_partial_credit():
    update = compute_posterior_update("wallet_X", "SURVIVOR")
    assert 0 < update.alpha_delta < 1.0


def test_thompson_sample_in_range():
    for _ in range(50):
        sample = sample_wallet_trust(alpha=5.0, beta=2.0)
        assert 0.0 <= sample <= 1.0


def test_high_alpha_produces_high_samples_on_average():
    """A wallet with many wins should sample high more often than not."""
    samples = [sample_wallet_trust(alpha=20.0, beta=2.0) for _ in range(200)]
    assert sum(samples) / len(samples) > 0.7


def test_classify_heavy_hitter():
    label = classify_outcome_from_returns(
        tradable_return_1h=3.0,
        max_return_24h=5.0,
        liquidity_7d=600_000,
        initial_liquidity=50_000,
    )
    assert label == "HEAVY_HITTER"


def test_classify_rug():
    label = classify_outcome_from_returns(
        tradable_return_1h=0.5,
        max_return_24h=1.2,
        liquidity_7d=50,        # near zero
        initial_liquidity=20_000,
    )
    assert label == "RUG"


def test_classify_tradeable_runner():
    label = classify_outcome_from_returns(
        tradable_return_1h=1.5,   # +50% tradable
        max_return_24h=2.0,
        liquidity_7d=10_000,
        initial_liquidity=8_000,
    )
    assert label == "TRADEABLE_RUNNER"


def test_update_all_wallet_scores_from_recent_outcomes_is_idempotent(monkeypatch):
    outcomes = [SimpleNamespace(id="outcome-1", token_mint="mint-1", label="TRADEABLE_RUNNER")]
    events = [SimpleNamespace(wallet_address="wallet-A")]
    claimed: set[tuple[str, str]] = set()
    saved = []

    async def fake_list_recent_completed_outcomes(_db, limit=500):
        return outcomes

    async def fake_get_wallet_events_for_token(_db, token_mint, event_type="BUY"):
        assert token_mint == "mint-1"
        return events

    async def fake_claim_wallet_outcome_application(_db, wallet_address, token_outcome_id, token_mint):
        del token_mint
        key = (wallet_address, token_outcome_id)
        if key in claimed:
            return False
        claimed.add(key)
        return True

    async def fake_get_wallet_beta_posterior(_db, address):
        return None

    async def fake_save_wallet_beta_posterior(_db, address, alpha, beta):
        saved.append((address, alpha, beta))
        return SimpleNamespace(wallet_address=address, alpha=alpha, beta=beta)

    monkeypatch.setattr("wigs.algorithms.feedback.alert_repo.list_recent_completed_outcomes", fake_list_recent_completed_outcomes)
    monkeypatch.setattr("wigs.algorithms.feedback.wallet_repo.get_wallet_events_for_token", fake_get_wallet_events_for_token)
    monkeypatch.setattr("wigs.algorithms.feedback.wallet_repo.claim_wallet_outcome_application", fake_claim_wallet_outcome_application)
    monkeypatch.setattr("wigs.algorithms.feedback.wallet_repo.get_wallet_beta_posterior", fake_get_wallet_beta_posterior)
    monkeypatch.setattr("wigs.algorithms.feedback.wallet_repo.save_wallet_beta_posterior", fake_save_wallet_beta_posterior)

    first = asyncio.run(update_all_wallet_scores_from_recent_outcomes(db=object()))
    second = asyncio.run(update_all_wallet_scores_from_recent_outcomes(db=object()))

    assert first == 1
    assert second == 0
    assert saved == [("wallet-A", 3.0, 2.0)]
