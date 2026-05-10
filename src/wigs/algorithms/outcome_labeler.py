"""Outcome measurement and labeling."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from wigs.algorithms.feedback import classify_outcome_from_returns
from wigs.clients import dexscreener, jupiter
from wigs.repositories import alert_repo


async def measure_tradable_return(
    token_mint: str,
    alert_time: datetime,
    window_hours: int,
    jupiter_client,
) -> float | None:
    """Approximate tradable return via current 1 SOL exit simulation."""
    del alert_time, window_hours
    try:
        report = await jupiter_client.estimate_sellability(token_mint)
    except Exception:
        return None
    if not report.route_exists or report.price_impact_1_sol is None:
        return None
    return max(0.0, 1.0 - report.price_impact_1_sol)


async def measure_liquidity_at_time(
    token_mint: str,
    target_time: datetime,
    dexscreener_client,
) -> float | None:
    del target_time
    try:
        pairs = await dexscreener_client.get_token_pairs(token_mint)
    except Exception:
        return None
    if not pairs:
        return None
    best = max(pairs, key=lambda pair: float(pair.get("liquidity", {}).get("usd", 0) or 0))
    return float(best.get("liquidity", {}).get("usd", 0) or 0)


async def label_token_outcome(
    token_mint: str,
    alert_id,
    alert_time: datetime,
    initial_liquidity_usd: float,
    jupiter_client,
    dexscreener_client,
    db: AsyncSession,
) -> str:
    tradable_return_1h = await measure_tradable_return(
        token_mint,
        alert_time,
        1,
        jupiter_client,
    )
    pairs = await dexscreener_client.get_token_pairs(token_mint)
    max_return_24h = None
    if pairs:
        best = max(pairs, key=lambda pair: float(pair.get("fdv", 0) or 0))
        price_change_h24 = float(best.get("priceChange", {}).get("h24", 0) or 0)
        max_return_24h = 1.0 + (price_change_h24 / 100.0)
    liquidity_7d = await measure_liquidity_at_time(
        token_mint,
        alert_time,
        dexscreener_client,
    )
    label = classify_outcome_from_returns(
        tradable_return_1h=tradable_return_1h,
        max_return_24h=max_return_24h,
        liquidity_7d=liquidity_7d,
        initial_liquidity=initial_liquidity_usd,
    )
    await alert_repo.save_outcome(
        db,
        token_mint=token_mint,
        alert_id=alert_id,
        label=label,
        tradable_return_1h=tradable_return_1h,
        max_return_24h=max_return_24h,
        measurement_complete=True,
        labeled_at=datetime.utcnow(),
    )
    return label
