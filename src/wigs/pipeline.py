"""Main event processing pipeline.

Entry point: handle_wallet_event()
  1. Parse and save the wallet event
  2. Extract candidate token mint
  3. Compute wallet convergence
  4. Enrich: market → sellability → safety → social → history
  5. Fuse all evidence into a final score
  6. Publish alert if score qualifies
  7. Write audit record
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from wigs.algorithms.convergence import BuyRecord, ConvergenceResult, compute_convergence_score
from wigs.algorithms.evidence_fusion import TokenScoreResult, compute_final_score
from wigs.algorithms.feedback import classify_outcome_from_returns
from wigs.algorithms.safety_veto import ConcentrationReport, RiskReport, compute_holder_concentration, evaluate
from wigs.algorithms.social_verifier import SocialScore, fetch_and_score
from wigs.clients import birdeye, dexscreener, geckoterminal, jupiter, solana_rpc
from wigs.config import get_settings
from wigs.models import (
    Alert,
    CandidateToken,
    SocialSnapshot,
    TokenMarketSnapshot,
    TokenOutcome,
    TokenRiskSnapshot,
    TokenScore,
    WalletEvent,
)

log = logging.getLogger(__name__)
settings = get_settings()

SOL_MINT = "So11111111111111111111111111111111111111112"


# ── Domain dataclasses ────────────────────────────────────────────────────────

@dataclass
class ParsedWalletEvent:
    wallet_address: str
    tx_signature: str
    token_mint: str | None
    event_type: str          # BUY / SELL / TRANSFER_IN / etc.
    amount_sol: float | None
    amount_usd: float | None
    amount_token: float | None
    dex_or_program: str | None
    pool_address: str | None
    event_time: datetime
    raw_payload: dict[str, Any]


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


# ── Helius webhook parsing ────────────────────────────────────────────────────

def parse_helius_event(payload: dict[str, Any], wallet_address: str) -> ParsedWalletEvent | None:
    """Extract a structured event from a raw Helius enhanced transaction payload."""
    try:
        tx_type = payload.get("type", "")
        sig = payload.get("signature", "")
        timestamp = payload.get("timestamp", 0)
        event_time = datetime.utcfromtimestamp(timestamp) if timestamp else datetime.utcnow()

        token_mint = None
        amount_sol = None
        amount_usd = None
        amount_token = None
        dex = None
        pool = None
        event_type = "BUY"

        # Enhanced transaction "tokenTransfers" field contains swap details
        for transfer in payload.get("tokenTransfers", []):
            if transfer.get("toUserAccount") == wallet_address:
                token_mint = transfer.get("mint")
                amount_token = float(transfer.get("tokenAmount", 0))
                break

        for native in payload.get("nativeTransfers", []):
            if native.get("fromUserAccount") == wallet_address:
                amount_sol = float(native.get("amount", 0)) / 1e9

        events = payload.get("events", {})
        swap = events.get("swap", {})
        if swap:
            dex = swap.get("programInfo", {}).get("source", "")
            if not token_mint:
                for out in swap.get("tokenOutputs", []):
                    token_mint = out.get("mint")
                    amount_token = float(out.get("rawTokenAmount", {}).get("tokenAmount", 0))

        if not token_mint or token_mint == SOL_MINT:
            return None

        return ParsedWalletEvent(
            wallet_address=wallet_address,
            tx_signature=sig,
            token_mint=token_mint,
            event_type=event_type,
            amount_sol=amount_sol,
            amount_usd=amount_usd,
            amount_token=amount_token,
            dex_or_program=dex,
            pool_address=pool,
            event_time=event_time,
            raw_payload=payload,
        )
    except Exception as exc:
        log.warning("Failed to parse Helius event: %s", exc)
        return None


# ── Market data fetching ──────────────────────────────────────────────────────

async def fetch_market_context(token_mint: str) -> MarketContext:
    """Fetch and reconcile market data from DexScreener + Birdeye."""
    dex_task = dexscreener.get_token_pairs(token_mint)
    bird_task = birdeye.get_token_overview(token_mint)

    dex_pairs, bird_data = await asyncio.gather(dex_task, bird_task, return_exceptions=True)
    if isinstance(dex_pairs, Exception):
        dex_pairs = []
    if isinstance(bird_data, Exception):
        bird_data = None

    # Use the highest-liquidity pair as primary
    best_pair: dict[str, Any] = {}
    if dex_pairs:
        best_pair = max(dex_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))

    liq = float(best_pair.get("liquidity", {}).get("usd", 0) or 0)
    price = float(best_pair.get("priceUsd", 0) or 0) or None
    volume = best_pair.get("volume", {})

    # Birdeye enrichment
    if bird_data:
        liq = liq or float(bird_data.get("liquidity", 0) or 0)
        price = price or float(bird_data.get("price", 0) or 0) or None

    return MarketContext(
        liquidity_usd=liq,
        price_usd=price,
        market_cap=float(best_pair.get("marketCap", 0) or 0) or None,
        fdv=float(best_pair.get("fdv", 0) or 0) or None,
        volume_5m=float(volume.get("m5", 0) or 0) or None,
        volume_1h=float(volume.get("h1", 0) or 0) or None,
        volume_24h=float(volume.get("h24", 0) or 0) or None,
        buyers_5m=best_pair.get("txns", {}).get("m5", {}).get("buys"),
        sellers_5m=best_pair.get("txns", {}).get("m5", {}).get("sells"),
        unique_buyers_5m=None,  # not available from DexScreener free tier
        avg_trade_size_usd=None,
        pool_age_minutes=None,   # computed from pool created_at if available
        primary_pool_address=best_pair.get("pairAddress"),
        source="dexscreener+birdeye",
    )


def score_market(ctx: MarketContext) -> int:
    """Compute market_score 0–100 from market context."""
    # Volume authenticity (unique_buyers / wash-trade proxy)
    vol_auth = 1.0
    if ctx.volume_5m and ctx.volume_5m > 0 and ctx.buyers_5m:
        avg_trade = (ctx.volume_5m / ctx.buyers_5m) if ctx.buyers_5m > 0 else ctx.volume_5m
        ratio = ctx.buyers_5m / (ctx.volume_5m / max(avg_trade, 1))
        vol_auth = min(1.0, ratio / 0.2)

    # Liquidity score (log-normalized)
    import math
    liq_score = min(1.0, math.log1p(ctx.liquidity_usd) / math.log1p(500_000))

    # Pool maturity
    maturity = 0.5  # default if unknown
    if ctx.pool_age_minutes is not None:
        maturity = min(1.0, ctx.pool_age_minutes / 60)  # 1h = full score

    raw = 0.40 * liq_score + 0.35 * vol_auth + 0.25 * maturity
    return min(100, max(0, int(raw * 100)))


# ── Safety enrichment ─────────────────────────────────────────────────────────

async def fetch_risk_data(
    token_mint: str,
    creator_wallet: str | None,
) -> tuple[ConcentrationReport, bool, bool, bool, bool, float | None, float | None, bool]:
    """Returns: concentration, mint_auth, freeze_auth, sell_exists, dev_dump, impact_1sol, impact_5sol, sell_ok"""
    supply_task = solana_rpc.get_token_supply(token_mint)
    holders_task = solana_rpc.get_token_largest_accounts(token_mint)
    bird_sec_task = birdeye.get_token_security(token_mint)
    sell_task = jupiter.estimate_sellability(token_mint)

    supply, holders, bird_sec, sell_report = await asyncio.gather(
        supply_task, holders_task, bird_sec_task, sell_task, return_exceptions=True
    )

    total_supply = float(supply.get("uiAmount", 0)) if isinstance(supply, dict) else 0.0
    holders_list = holders if isinstance(holders, list) else []
    concentration = compute_holder_concentration(holders_list, total_supply or 1.0)

    mint_auth = False
    freeze_auth = False
    if isinstance(bird_sec, dict):
        mint_auth = bool(bird_sec.get("mintAuthorityAddress"))
        freeze_auth = bool(bird_sec.get("freezeAuthorityAddress"))

    if isinstance(sell_report, Exception):
        sell_report = jupiter.SellabilityReport(
            route_exists=False, price_impact_025_sol=None,
            price_impact_1_sol=None, price_impact_5_sol=None, all_quotes_succeeded=False
        )

    return (
        concentration,
        mint_auth,
        freeze_auth,
        sell_report.route_exists,
        False,  # dev_dump — requires creator wallet tx analysis (Phase 2 feature)
        sell_report.price_impact_1_sol,
        sell_report.price_impact_5_sol,
        sell_report.all_quotes_succeeded,
    )


# ── Convergence loading ───────────────────────────────────────────────────────

async def load_convergence_buyers(token_mint: str, db: AsyncSession) -> list[BuyRecord]:
    """Load all tracked wallet buy records for this token from the DB."""
    from sqlalchemy import select, text
    from wigs.models import WalletClusterMember, WalletScoreSnapshot

    # Get all buy events for this token
    stmt = select(WalletEvent).where(
        WalletEvent.token_mint == token_mint,
        WalletEvent.event_type == "BUY",
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    buy_records: list[BuyRecord] = []
    for evt in events:
        # Get wallet quality score
        score_stmt = (
            select(WalletScoreSnapshot)
            .where(WalletScoreSnapshot.wallet_address == evt.wallet_address)
            .order_by(WalletScoreSnapshot.captured_at.desc())
            .limit(1)
        )
        score_result = await db.execute(score_stmt)
        score = score_result.scalar_one_or_none()
        quality = score.wallet_quality if score else 50

        # Get cluster membership
        cluster_stmt = select(WalletClusterMember).where(
            WalletClusterMember.wallet_address == evt.wallet_address
        )
        cluster_result = await db.execute(cluster_stmt)
        membership = cluster_result.scalar_one_or_none()

        cluster_id = str(membership.cluster_id) if membership else None
        cluster_type = None
        cluster_size = 1

        if membership:
            from sqlalchemy import func as sqlfunc
            from wigs.models import WalletCluster
            cluster_info_stmt = select(WalletCluster).where(
                WalletCluster.id == membership.cluster_id
            )
            cluster_result2 = await db.execute(cluster_info_stmt)
            cluster_obj = cluster_result2.scalar_one_or_none()
            if cluster_obj:
                cluster_type = cluster_obj.cluster_type
                # Count cluster members
                count_stmt = select(WalletClusterMember).where(
                    WalletClusterMember.cluster_id == membership.cluster_id
                )
                count_result = await db.execute(count_stmt)
                cluster_size = len(count_result.scalars().all())

        buy_records.append(BuyRecord(
            wallet_address=evt.wallet_address,
            wallet_quality=quality,
            event_time=evt.event_time,
            cluster_id=cluster_id,
            cluster_type=cluster_type,
            cluster_size=cluster_size,
        ))

    return buy_records


# ── Main orchestration ────────────────────────────────────────────────────────

async def handle_wallet_event(
    raw_payload: dict[str, Any],
    wallet_address: str,
    db: AsyncSession,
) -> TokenScoreResult | None:
    """
    Full pipeline entry point. Called for every Helius webhook event.
    Returns a scored result if the event produced a candidate, else None.
    """
    event = parse_helius_event(raw_payload, wallet_address)
    if not event or event.event_type != "BUY" or not event.token_mint:
        return None

    # ── 1. Persist the wallet event ──────────────────────────────────────
    db_event = WalletEvent(
        wallet_address=event.wallet_address,
        tx_signature=event.tx_signature,
        token_mint=event.token_mint,
        event_type=event.event_type,
        amount_sol=event.amount_sol,
        amount_usd=event.amount_usd,
        amount_token=event.amount_token,
        dex_or_program=event.dex_or_program,
        pool_address=event.pool_address,
        event_time=event.event_time,
        raw_payload=event.raw_payload,
    )
    db.add(db_event)

    # ── 2. Upsert candidate token ────────────────────────────────────────
    from sqlalchemy import select
    existing = await db.execute(
        select(CandidateToken).where(CandidateToken.token_mint == event.token_mint)
    )
    candidate = existing.scalar_one_or_none()
    if candidate is None:
        candidate = CandidateToken(
            token_mint=event.token_mint,
            first_seen_at=datetime.utcnow(),
            status="ENRICHING",
        )
        db.add(candidate)

    await db.flush()  # get IDs without committing

    # ── 3. Convergence ───────────────────────────────────────────────────
    buyers = await load_convergence_buyers(event.token_mint, db)
    convergence = compute_convergence_score(buyers)

    # ── 4. Parallel enrichment ───────────────────────────────────────────
    market_task = fetch_market_context(event.token_mint)
    risk_task = fetch_risk_data(event.token_mint, candidate.creator_wallet)
    social_task = fetch_and_score(event.token_mint, candidate.symbol, candidate.name)

    market_ctx, risk_data, social_score = await asyncio.gather(
        market_task, risk_task, social_task, return_exceptions=True
    )

    if isinstance(market_ctx, Exception):
        log.error("Market fetch failed for %s: %s", event.token_mint, market_ctx)
        market_ctx = MarketContext(
            liquidity_usd=0, price_usd=None, market_cap=None, fdv=None,
            volume_5m=None, volume_1h=None, volume_24h=None, buyers_5m=None,
            sellers_5m=None, unique_buyers_5m=None, avg_trade_size_usd=None,
            pool_age_minutes=None, primary_pool_address=None, source="error",
        )
    if isinstance(social_score, Exception):
        from wigs.algorithms.social_verifier import SocialEvidence, SocialScore
        social_score = SocialScore(value=0, evidence=SocialEvidence())
    if isinstance(risk_data, Exception):
        from wigs.algorithms.safety_veto import ConcentrationReport
        risk_data = (
            ConcentrationReport(gini=0, hhi=0, top_10_pct=0, top_20_pct=0, holder_count=0),
            None, None, False, False, None, None, False
        )

    (concentration, mint_auth, freeze_auth, sell_exists,
     dev_dump, impact_1sol, impact_5sol, sell_ok) = risk_data

    # ── 5. Safety veto evaluation ────────────────────────────────────────
    vol_auth_ratio = None
    if market_ctx.volume_5m and market_ctx.buyers_5m:
        vol_auth_ratio = market_ctx.buyers_5m / max(1, market_ctx.volume_5m / 100)

    risk_report = evaluate(
        liquidity_usd=market_ctx.liquidity_usd,
        mint_authority_active=mint_auth,
        freeze_authority_active=freeze_auth,
        concentration=concentration,
        sell_quote_exists=sell_exists,
        price_impact_1_sol=impact_1sol,
        price_impact_5_sol=impact_5sol,
        pool_age_minutes=market_ctx.pool_age_minutes,
        volume_authenticity_ratio=vol_auth_ratio,
        has_social_data=social_score.value > 0,
        independent_buyer_count=convergence.independent_buyer_count,
        cluster_is_independent=convergence.independent_buyer_count > 0,
        kol_already_called=False,    # TODO: implement KOL call detection
        dev_dump_detected=dev_dump,
        copycat_mint=False,          # TODO: implement copycat detection
        social_drainer_link=False,   # TODO: implement link scanning
    )

    # ── 6. Score components ──────────────────────────────────────────────
    market_score = score_market(market_ctx)
    wallet_score = min(100, int(
        0.70 * convergence.convergence_score
        + 0.30 * (buyers[0].wallet_quality if buyers else 50)
    ))
    history_score = 50   # TODO: implement history analyzer
    execution_score = sell_ok and not risk_report.has_hard_veto() and (
        (impact_1sol or 1.0) < settings.max_price_impact_1_sol
    )
    execution_score_int = 100 if execution_score else 30

    # ── 7. Evidence fusion ───────────────────────────────────────────────
    result = compute_final_score(
        wallet_score=wallet_score,
        market_score=market_score,
        risk_report=risk_report,
        social_score=social_score,
        history_score=history_score,
        execution_score=execution_score_int,
        convergence=convergence,
    )

    # ── 8. Persist snapshots and score ───────────────────────────────────
    db.add(TokenMarketSnapshot(
        token_mint=event.token_mint,
        liquidity_usd=market_ctx.liquidity_usd,
        price_usd=market_ctx.price_usd,
        market_cap=market_ctx.market_cap,
        fdv=market_ctx.fdv,
        volume_5m=market_ctx.volume_5m,
        volume_1h=market_ctx.volume_1h,
        volume_24h=market_ctx.volume_24h,
        buyers_5m=market_ctx.buyers_5m,
        sellers_5m=market_ctx.sellers_5m,
        source=market_ctx.source,
    ))
    db.add(TokenRiskSnapshot(
        token_mint=event.token_mint,
        mint_authority_active=mint_auth,
        freeze_authority_active=freeze_auth,
        top_10_holder_pct=concentration.top_10_pct,
        top_20_holder_pct=concentration.top_20_pct,
        gini_coefficient=concentration.gini,
        hhi=concentration.hhi,
        sell_quote_exists=sell_exists,
        price_impact_1_sol=impact_1sol,
        price_impact_5_sol=impact_5sol,
        risk_flags=result.score_reasons.get("vetoes", []),
        risk_score=result.risk_score,
    ))
    db.add(SocialSnapshot(
        token_mint=event.token_mint,
        reddit_mentions=social_score.evidence.reddit_mentions,
        telegram_mentions=social_score.evidence.telegram_mentions,
        discord_mentions=social_score.evidence.discord_mentions,
        youtube_mentions=social_score.evidence.youtube_mentions,
        gdelt_mentions=social_score.evidence.gdelt_mentions,
        unique_sources=social_score.evidence.unique_sources,
        velocity_acceleration=social_score.evidence.velocity_acceleration,
        novelty_score=social_score.evidence.novelty_score,
        social_score=social_score.value,
    ))

    token_score = TokenScore(
        token_mint=event.token_mint,
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
    db.add(token_score)

    # Update candidate status
    candidate.status = result.decision if result.decision != "AVOID" else "REJECTED"
    await db.flush()

    # ── 9. Alert ─────────────────────────────────────────────────────────
    if result.decision in ("STRONG_WATCH", "STRONG_CANDIDATE"):
        from wigs.alerts import publish_alert
        await publish_alert(candidate, token_score, db)

    log.info(
        "Scored %s | decision=%s | total=%d | wallets=%d | spread=%.0fs",
        event.token_mint,
        result.decision,
        result.total_score,
        convergence.independent_buyer_count,
        convergence.time_spread_seconds,
    )

    return result
