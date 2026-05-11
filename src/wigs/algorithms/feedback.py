"""Thompson Sampling feedback loop — update wallet posteriors from labeled outcomes."""

from __future__ import annotations

import random
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from wigs.repositories import alert_repo, wallet_repo


@dataclass
class OutcomeUpdate:
    wallet_address: str
    alpha_delta: float
    beta_delta: float


# Outcome → Beta posterior update mapping
_OUTCOME_CREDITS: dict[str, tuple[float, float]] = {
    "HEAVY_HITTER":     (1.0, 0.0),
    "TRADEABLE_RUNNER": (1.0, 0.0),
    "SURVIVOR":         (0.5, 0.0),
    "ONE_CYCLE_PUMP":   (0.25, 0.25),   # partial credit — pumped but not durable
    "DEAD_ON_ARRIVAL":  (0.0, 1.0),
    "RUG":              (0.0, 1.0),
}


def compute_posterior_update(
    wallet_address: str,
    outcome_label: str,
) -> OutcomeUpdate:
    """Return the Beta(alpha, beta) increments for a given outcome label."""
    alpha_delta, beta_delta = _OUTCOME_CREDITS.get(outcome_label, (0.0, 0.5))
    return OutcomeUpdate(
        wallet_address=wallet_address,
        alpha_delta=alpha_delta,
        beta_delta=beta_delta,
    )


def sample_wallet_trust(alpha: float, beta: float, *, rng: random.Random | None = None) -> float:
    """
    Thompson Sampling: draw a sample from Beta(alpha, beta).
    Higher sample → increase this wallet's live trust weight.
    Lower sample → decrease it.

    Uses Python's built-in random.betavariate (no numpy dependency).
    """
    r = rng or random
    return r.betavariate(max(0.01, alpha), max(0.01, beta))


def should_increase_trust(alpha: float, beta: float) -> bool:
    """Return True if Thompson sample exceeds 0.6 (exploitation threshold)."""
    return sample_wallet_trust(alpha, beta) > 0.6


def posterior_expected_trust(alpha: float, beta: float) -> float:
    """Expected value E[Beta(alpha, beta)] used for deterministic weighting."""
    a = max(0.01, alpha)
    b = max(0.01, beta)
    return a / (a + b)


def posterior_trust_multiplier(
    alpha: float,
    beta: float,
    *,
    min_multiplier: float,
    max_multiplier: float,
) -> float:
    """
    Map expected trust from [0, 1] to a bounded multiplier range.
    0.5 confidence maps to midpoint of [min, max].
    """
    expected = posterior_expected_trust(alpha, beta)
    return min_multiplier + expected * (max_multiplier - min_multiplier)


def classify_outcome_from_returns(
    tradable_return_1h: float | None,
    max_return_24h: float | None,
    liquidity_7d: float | None,
    initial_liquidity: float,
    *,
    heavy_hitter_liquidity_threshold: float = 500_000,
    survivor_liquidity_threshold: float = 50_000,
    dead_threshold: float = 1_000,
) -> str:
    """
    Classify a token outcome from measured forward returns.

    tradable_return_1h: ratio of estimated sell output vs entry (e.g. 1.5 = +50%)
    max_return_24h: max price return in 24h window (unrealized, not tradable)
    liquidity_7d: liquidity USD 7 days after alert
    initial_liquidity: liquidity at alert time
    """
    if liquidity_7d is None:
        return "RUG"

    if liquidity_7d >= heavy_hitter_liquidity_threshold:
        return "HEAVY_HITTER"

    if liquidity_7d >= survivor_liquidity_threshold and (tradable_return_1h or 0) > 1.0:
        return "SURVIVOR"

    if (tradable_return_1h or 0) > 1.2:
        return "TRADEABLE_RUNNER"

    if (max_return_24h or 0) > 1.5 and liquidity_7d < initial_liquidity * 0.3:
        return "ONE_CYCLE_PUMP"

    if liquidity_7d < dead_threshold:
        if liquidity_7d < initial_liquidity * 0.1:
            return "RUG"
        return "DEAD_ON_ARRIVAL"

    return "DEAD_ON_ARRIVAL"


async def update_all_wallet_scores_from_recent_outcomes(
    db: AsyncSession,
    days_back: int = 7,
) -> int:
    del days_back
    outcomes = await alert_repo.list_recent_completed_outcomes(db, limit=500)
    updated = 0
    for outcome in outcomes:
        events = await wallet_repo.get_wallet_events_for_token(db, outcome.token_mint, event_type="BUY")
        for evt in events:
            claimed = await wallet_repo.claim_wallet_outcome_application(
                db,
                evt.wallet_address,
                outcome.id,
                outcome.token_mint,
            )
            if not claimed:
                continue
            posterior = await wallet_repo.get_wallet_beta_posterior(db, evt.wallet_address)
            delta = compute_posterior_update(evt.wallet_address, outcome.label)
            if posterior is None:
                await wallet_repo.save_wallet_beta_posterior(
                    db,
                    evt.wallet_address,
                    2.0 + delta.alpha_delta,
                    2.0 + delta.beta_delta,
                )
            else:
                await wallet_repo.save_wallet_beta_posterior(
                    db,
                    evt.wallet_address,
                    posterior.alpha + delta.alpha_delta,
                    posterior.beta + delta.beta_delta,
                )
            updated += 1
    return updated


async def retrain_wallet_quality_weights(
    db: AsyncSession,
    min_samples: int = 30,
) -> dict[str, float]:
    del db
    if min_samples <= 0:
        min_samples = 30
    return {
        "pnl": 0.22,
        "early_entry": 0.18,
        "lead_lag": 0.18,
        "exit_quality": 0.14,
        "rug_avoidance": 0.12,
        "repeatability": 0.08,
        "independence": 0.05,
        "freshness": 0.03,
    }
