"""Market-context enrichment and scoring."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from wigs.clients import birdeye, dexscreener, geckoterminal


@dataclass
class MarketContext:
    liquidity_usd: float
    price_usd: float | None
    market_cap: float | None
    fdv: float | None
    volume_5m: float | None
    volume_1h: float | None
    volume_24h: float | None
    buyers_5m: int | None
    sellers_5m: int | None
    unique_buyers_5m: int | None
    avg_trade_size_usd: float | None
    pool_age_minutes: float | None
    primary_pool_address: str | None
    source: str


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def check_volume_authenticity(
    volume_5m: float,
    buyers_5m: int,
    avg_trade_size_usd: float,
) -> float:
    if volume_5m <= 0 or buyers_5m <= 0 or avg_trade_size_usd <= 0:
        return 0.0
    unique_buyer_ratio = buyers_5m / max(1.0, volume_5m / avg_trade_size_usd)
    return max(0.0, min(1.0, unique_buyer_ratio / 0.2))


async def fetch_market_context(token_mint: str) -> MarketContext:
    """Reconcile DexScreener + GeckoTerminal + Birdeye."""
    dex_task = dexscreener.get_token_pairs(token_mint)
    gecko_task = geckoterminal.get_token_pools(token_mint, network="solana")
    bird_task = birdeye.get_token_overview(token_mint)

    dex_pairs, gecko_pools, bird_data = await asyncio.gather(
        dex_task,
        gecko_task,
        bird_task,
        return_exceptions=True,
    )
    if isinstance(dex_pairs, Exception):
        dex_pairs = []
    if isinstance(gecko_pools, Exception):
        gecko_pools = []
    if isinstance(bird_data, Exception):
        bird_data = None

    best_pair: dict[str, Any] = {}
    if dex_pairs:
        best_pair = max(dex_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))

    price = float(best_pair.get("priceUsd", 0) or 0) or None
    liquidity = float(best_pair.get("liquidity", {}).get("usd", 0) or 0)
    volume = best_pair.get("volume", {}) or {}
    buyers_5m = best_pair.get("txns", {}).get("m5", {}).get("buys")
    sellers_5m = best_pair.get("txns", {}).get("m5", {}).get("sells")
    pair_created_at = _parse_iso8601(best_pair.get("pairCreatedAt")) or None
    pool_address = best_pair.get("pairAddress")
    pool_age_minutes = None
    if pair_created_at is not None:
        now = datetime.now(timezone.utc)
        pair_dt = pair_created_at if pair_created_at.tzinfo else pair_created_at.replace(tzinfo=timezone.utc)
        pool_age_minutes = max(0.0, (now - pair_dt).total_seconds() / 60.0)

    gecko_best = None
    if gecko_pools:
        gecko_best = max(
            gecko_pools,
            key=lambda p: float(p.get("attributes", {}).get("reserve_in_usd", 0) or 0),
        )
        attrs = gecko_best.get("attributes", {})
        liquidity = liquidity or float(attrs.get("reserve_in_usd", 0) or 0)
        price = price or float(attrs.get("base_token_price_usd", 0) or 0) or None
        if pool_age_minutes is None:
            created_at = _parse_iso8601(attrs.get("pool_created_at"))
            if created_at:
                now = datetime.now(timezone.utc)
                pool_age_minutes = max(0.0, (now - created_at).total_seconds() / 60.0)
        pool_address = pool_address or gecko_best.get("id", "").split("_")[-1]

    if bird_data:
        liquidity = liquidity or float(bird_data.get("liquidity", 0) or 0)
        price = price or float(bird_data.get("price", 0) or 0) or None

    avg_trade_size_usd = None
    volume_5m = float(volume.get("m5", 0) or 0) or None
    if volume_5m and buyers_5m:
        avg_trade_size_usd = volume_5m / max(1, buyers_5m)

    return MarketContext(
        liquidity_usd=liquidity,
        price_usd=price,
        market_cap=float(best_pair.get("marketCap", 0) or 0) or None,
        fdv=float(best_pair.get("fdv", 0) or 0) or None,
        volume_5m=volume_5m,
        volume_1h=float(volume.get("h1", 0) or 0) or None,
        volume_24h=float(volume.get("h24", 0) or 0) or None,
        buyers_5m=buyers_5m,
        sellers_5m=sellers_5m,
        unique_buyers_5m=buyers_5m,
        avg_trade_size_usd=avg_trade_size_usd,
        pool_age_minutes=pool_age_minutes,
        primary_pool_address=pool_address,
        source="dexscreener+geckoterminal+birdeye",
    )


def score_market_context(ctx: MarketContext) -> int:
    liq_score = min(1.0, math.log1p(max(0.0, ctx.liquidity_usd)) / math.log1p(500_000))
    vol_auth = 0.0
    if ctx.volume_5m and ctx.buyers_5m and ctx.avg_trade_size_usd:
        vol_auth = check_volume_authenticity(ctx.volume_5m, ctx.buyers_5m, ctx.avg_trade_size_usd)
    maturity = 0.5 if ctx.pool_age_minutes is None else min(1.0, ctx.pool_age_minutes / 60.0)
    raw = 0.40 * liq_score + 0.35 * vol_auth + 0.25 * maturity
    return max(0, min(100, int(raw * 100)))
