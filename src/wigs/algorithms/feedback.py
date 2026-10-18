"""Thompson Sampling feedback loop — update wallet posteriors from labeled outcomes."""

from __future__ import annotations

import random
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from wigs.filters import (
    OUTCOME_BETA_CREDITS,
    THOMPSON_TRUST_THRESHOLD,
    classify_outcome as _classify_outcome_fn,
)
from wigs.repositories import alert_repo, wallet_repo


@dataclass
class OutcomeUpdate:
    wallet_address: str
    alpha_delta: float
    beta_delta: float


def compute_posterior_update(
    wallet_address: str,
    outcome_label: str,
) -> OutcomeUpdate:
    """Return the Beta(alpha, beta) increments for a given outcome label."""
    alpha_delta, beta_delta = OUTCOME_BETA_CREDITS.get(outcome_label, (0.0, 0.5))
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
    """Return True if Thompson sample exceeds THOMPSON_TRUST_THRESHOLD (defined in filters.py)."""
    return sample_wallet_trust(alpha, beta) > THOMPSON_TRUST_THRESHOLD


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
    heavy_hitter_liquidity_threshold: float | None = None,
    survivor_liquidity_threshold: float | None = None,
    dead_threshold: float | None = None,
) -> str:
    """Delegate to filters.classify_outcome — single source of truth.

    The threshold kwargs are accepted for backwards compatibility but ignored;
    all thresholds are now defined in filters.py.
    """
    return _classify_outcome_fn(tradable_return_1h, max_return_24h, liquidity_7d, initial_liquidity)


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
