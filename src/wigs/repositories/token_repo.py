"""Token-oriented repository helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from wigs.models import (
    CandidateToken,
    SocialSnapshot,
    TokenMarketSnapshot,
    TokenRiskSnapshot,
    TokenScore,
)


async def upsert_candidate_token(
    db: AsyncSession,
    mint: str,
    **kwargs: Any,
) -> CandidateToken:
    result = await db.execute(
        select(CandidateToken).where(CandidateToken.token_mint == mint)
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        candidate = CandidateToken(token_mint=mint, **kwargs)
        db.add(candidate)
    else:
        for key, value in kwargs.items():
            if value is not None and hasattr(candidate, key):
                setattr(candidate, key, value)
    await db.flush()
    return candidate


async def get_candidate_token(db: AsyncSession, mint: str) -> CandidateToken | None:
    result = await db.execute(
        select(CandidateToken).where(CandidateToken.token_mint == mint)
    )
    return result.scalar_one_or_none()


async def save_market_snapshot(db: AsyncSession, mint: str, ctx: Any) -> TokenMarketSnapshot:
    snapshot = TokenMarketSnapshot(
        token_mint=mint,
        liquidity_usd=ctx.liquidity_usd,
        price_usd=ctx.price_usd,
        market_cap=ctx.market_cap,
        fdv=ctx.fdv,
        volume_5m=ctx.volume_5m,
        volume_1h=ctx.volume_1h,
        volume_24h=ctx.volume_24h,
        buyers_5m=ctx.buyers_5m,
        sellers_5m=ctx.sellers_5m,
        unique_buyers_5m=ctx.unique_buyers_5m,
        avg_trade_size_usd=ctx.avg_trade_size_usd,
        pool_age_minutes=ctx.pool_age_minutes,
        primary_pool_address=ctx.primary_pool_address,
        source=ctx.source,
    )
    db.add(snapshot)
    await db.flush()
    return snapshot


async def save_risk_snapshot(
    db: AsyncSession,
    mint: str,
    risk: Any,
    concentration: Any,
    *,
    mint_authority_active: bool | None = None,
    freeze_authority_active: bool | None = None,
    sell_quote_exists: bool = False,
    price_impact_025_sol: float | None = None,
    price_impact_1_sol: float | None = None,
    price_impact_5_sol: float | None = None,
    dev_holding_pct: float | None = None,
) -> TokenRiskSnapshot:
    flags = []
    if hasattr(risk, "vetoes") and risk.vetoes:
        flags.extend(risk.vetoes)
    if hasattr(risk, "penalties") and risk.penalties:
        flags.extend(p[0] if isinstance(p, tuple) else p for p in risk.penalties)

    snapshot = TokenRiskSnapshot(
        token_mint=mint,
        mint_authority_active=mint_authority_active,
        freeze_authority_active=freeze_authority_active,
        top_10_holder_pct=concentration.top_10_pct,
        top_20_holder_pct=concentration.top_20_pct,
        dev_holding_pct=dev_holding_pct,
        gini_coefficient=concentration.gini,
        hhi=concentration.hhi,
        sell_quote_exists=sell_quote_exists,
        price_impact_025_sol=price_impact_025_sol,
        price_impact_1_sol=price_impact_1_sol,
        price_impact_5_sol=price_impact_5_sol,
        risk_flags=flags or None,
        risk_score=getattr(risk, "risk_score", 0),
    )
    db.add(snapshot)
    await db.flush()
    return snapshot


async def save_social_snapshot(db: AsyncSession, mint: str, social: Any) -> SocialSnapshot:
    evidence = social.evidence
    snapshot = SocialSnapshot(
        token_mint=mint,
        reddit_mentions=evidence.reddit_mentions,
        telegram_mentions=evidence.telegram_mentions,
        discord_mentions=evidence.discord_mentions,
        youtube_mentions=evidence.youtube_mentions,
        gdelt_mentions=evidence.gdelt_mentions,
        unique_sources=evidence.unique_sources,
        velocity_acceleration=evidence.velocity_acceleration,
        novelty_score=evidence.novelty_score,
        organic_ratio=evidence.organic_ratio,
        social_score=social.value,
    )
    db.add(snapshot)
    await db.flush()
    return snapshot


async def save_token_score(db: AsyncSession, result: Any, mint: str) -> TokenScore:
    score = TokenScore(
        token_mint=mint,
        wallet_score=result.wallet_score,
        market_score=result.market_score,
        risk_score=result.risk_score,
        social_score=result.social_score,
        history_score=result.history_score,
        execution_score=result.execution_score,
        total_score=result.total_score,
        decision=result.decision,
        risk_level=result.risk_level,
        convergence_independent_count=result.convergence_independent_count,
        convergence_time_spread_s=result.convergence_time_spread_s,
        threshold_adjustment=result.threshold_adjustment,
        score_reasons=result.score_reasons,
    )
    db.add(score)
    await db.flush()
    return score


async def get_latest_token_context(db: AsyncSession, mint: str) -> dict[str, Any]:
    market_result = await db.execute(
        select(TokenMarketSnapshot)
        .where(TokenMarketSnapshot.token_mint == mint)
        .order_by(desc(TokenMarketSnapshot.captured_at))
        .limit(1)
    )
    risk_result = await db.execute(
        select(TokenRiskSnapshot)
        .where(TokenRiskSnapshot.token_mint == mint)
        .order_by(desc(TokenRiskSnapshot.captured_at))
        .limit(1)
    )
    social_result = await db.execute(
        select(SocialSnapshot)
        .where(SocialSnapshot.token_mint == mint)
        .order_by(desc(SocialSnapshot.captured_at))
        .limit(1)
    )
    score_result = await db.execute(
        select(TokenScore)
        .where(TokenScore.token_mint == mint)
        .order_by(desc(TokenScore.created_at))
        .limit(1)
    )
    return {
        "market": market_result.scalar_one_or_none(),
        "risk": risk_result.scalar_one_or_none(),
        "social": social_result.scalar_one_or_none(),
        "score": score_result.scalar_one_or_none(),
    }


async def get_latest_token_score(db: AsyncSession, mint: str) -> TokenScore | None:
    result = await db.execute(
        select(TokenScore)
        .where(TokenScore.token_mint == mint)
        .order_by(desc(TokenScore.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_open_candidates(
    db: AsyncSession,
    statuses: list[str],
) -> list[CandidateToken]:
    result = await db.execute(
        select(CandidateToken).where(CandidateToken.status.in_(statuses))
    )
    return list(result.scalars().all())
