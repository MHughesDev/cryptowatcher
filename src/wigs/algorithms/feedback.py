"""Thompson Sampling feedback loop — update wallet posteriors from labeled outcomes."""

from __future__ import annotations

import random
from dataclasses import dataclass


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
