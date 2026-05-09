"""Tests for Thompson Sampling feedback loop."""

from wigs.algorithms.feedback import (
    classify_outcome_from_returns,
    compute_posterior_update,
    sample_wallet_trust,
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
