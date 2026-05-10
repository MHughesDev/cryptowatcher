"""Historical context scoring for creators and early holders."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from wigs.clients import dexscreener
from wigs.repositories import token_repo, wallet_repo


async def score_creator_reputation(
    creator_wallet: str | None,
    solana_rpc_client,
    helius_client,
) -> float:
    if not creator_wallet:
        return 50.0

    txs = await helius_client.get_transactions_for_address(creator_wallet, limit=100)
    launch_events = [
        tx for tx in txs
        if tx.get("type") in {"CREATE_POOL", "TOKEN_MINT", "CREATE_TOKEN"}
        or tx.get("token_mint")
        or tx.get("mint")
    ]
    prior_count = max(0, len(launch_events) - 1)
    rug_count = sum(1 for tx in launch_events if tx.get("suspected_rug") or tx.get("rug"))
    if prior_count <= 0:
        return 50.0
    survivor_ratio = max(0.0, min(1.0, (prior_count - rug_count) / prior_count))
    score = 100.0 * (0.7 * survivor_ratio + 0.3 * min(1.0, prior_count / 10.0))
    return max(0.0, min(100.0, score))


async def score_early_holder_quality(
    token_mint: str,
    db: AsyncSession,
) -> float:
    buyers = await wallet_repo.get_wallet_events_for_token(db, token_mint, event_type="BUY")
    if not buyers:
        return 50.0
    first_ten = buyers[:10]
    qualities = []
    for buyer in first_ten:
        snapshot = await wallet_repo.get_wallet_score(db, buyer.wallet_address)
        qualities.append(snapshot.wallet_quality if snapshot else 50)
    return sum(qualities) / len(qualities)


async def score_launch_context(
    token_mint: str,
    pool_age_minutes: float,
    initial_liquidity_usd: float,
    paid_boost_detected: bool,
) -> float:
    liq_component = min(1.0, max(0.0, initial_liquidity_usd / 5_000.0))
    age_component = min(1.0, max(0.0, pool_age_minutes / 5.0))
    boost_component = 0.0 if paid_boost_detected else 1.0
    score = (0.45 * liq_component + 0.35 * age_component + 0.20 * boost_component) * 100.0
    return max(0.0, min(100.0, score))


async def analyze(
    token_mint: str,
    creator_wallet: str | None,
    pool_age_minutes: float,
    db: AsyncSession,
    solana_rpc_client,
    helius_client,
) -> int:
    creator_reputation = await score_creator_reputation(
        creator_wallet,
        solana_rpc_client,
        helius_client,
    )
    early_holder_quality = await score_early_holder_quality(token_mint, db)
    market_ctx = await token_repo.get_latest_token_context(db, token_mint)
    latest_market = market_ctx.get("market")
    initial_liquidity_usd = latest_market.liquidity_usd if latest_market else 0.0
    paid_boost_detected = bool(await dexscreener.get_paid_orders(token_mint))
    launch_context = await score_launch_context(
        token_mint,
        pool_age_minutes=pool_age_minutes or 0.0,
        initial_liquidity_usd=initial_liquidity_usd,
        paid_boost_detected=paid_boost_detected,
    )
    total = (
        0.50 * creator_reputation
        + 0.30 * early_holder_quality
        + 0.20 * launch_context
    )
    return max(0, min(100, int(total)))
