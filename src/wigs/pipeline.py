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
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from wigs.algorithms.convergence import BuyRecord, ConvergenceResult, compute_convergence_score
from wigs.algorithms.evidence_fusion import TokenScoreResult, compute_final_score
from wigs.algorithms.execution_verifier import check_sellability, score_execution
from wigs.algorithms.history_analyzer import analyze as analyze_history
from wigs.algorithms.market_verifier import fetch_market_context as fetch_market_context_impl, score_market_context
from wigs.algorithms.safety_veto import ConcentrationReport, RiskReport, compute_holder_concentration, evaluate
from wigs.algorithms.social_verifier import SocialScore, fetch_and_score
from wigs.clients import birdeye, helius, jupiter, solana_rpc
from wigs.config import get_settings
from wigs.models import CandidateToken, TrackedWallet, WalletEvent
from wigs.repositories import graph_repo, token_repo, wallet_repo

log = logging.getLogger(__name__)
settings = get_settings()

SOL_MINT = "So11111111111111111111111111111111111111112"
KNOWN_LEGITIMATE_TOKENS = {
    ("solana", "sol"),
    ("usd coin", "usdc"),
    ("tether", "usdt"),
    ("wrapped sol", "wsol"),
}
MALICIOUS_PATTERNS = [
    re.compile(r"wallet[- ]?connect", re.IGNORECASE),
    re.compile(r"free\s+mint.*connect wallet", re.IGNORECASE),
    re.compile(r"(claim|airdrop).*(seed phrase|private key)", re.IGNORECASE),
    re.compile(r"https?://[^\s]*(drain|airdrop|claim-now|walletbonus)[^\s]*", re.IGNORECASE),
]


class AuditLedger:
    @staticmethod
    def record_decision(
        token_mint: str,
        decision: str,
        total_score: int,
        score_breakdown: dict[str, Any],
        convergence_wallets: int,
        triggered_by_wallet: str,
    ) -> None:
        logger = structlog.get_logger("audit")
        logger.info(
            "decision",
            token_mint=token_mint,
            decision=decision,
            total_score=total_score,
            convergence_wallets=convergence_wallets,
            triggered_by_wallet=triggered_by_wallet,
            **score_breakdown,
        )


def _normalize_token_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        curr = [i]
        for j, char_b in enumerate(b, start=1):
            insertions = prev[j] + 1
            deletions = curr[j - 1] + 1
            substitutions = prev[j - 1] + (char_a != char_b)
            curr.append(min(insertions, deletions, substitutions))
        prev = curr
    return prev[-1]


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
    return await fetch_market_context_impl(token_mint)


def score_market(ctx: MarketContext) -> int:
    return score_market_context(ctx)


# ── Safety enrichment ─────────────────────────────────────────────────────────

async def fetch_risk_data(
    token_mint: str,
    creator_wallet: str | None,
) -> tuple[ConcentrationReport, bool, bool, bool, jupiter.SellabilityReport]:
    """Returns: concentration, mint_auth, freeze_auth, dev_dump, sell_report"""
    supply_task = solana_rpc.get_token_supply(token_mint)
    holders_task = solana_rpc.get_token_largest_accounts(token_mint)
    bird_sec_task = birdeye.get_token_security(token_mint)
    sell_task = check_sellability(token_mint)

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

    return (concentration, mint_auth, freeze_auth, False, sell_report)


# ── Convergence loading ───────────────────────────────────────────────────────

async def load_convergence_buyers(token_mint: str, db: AsyncSession) -> list[BuyRecord]:
    """Load all tracked wallet buy records for this token from the DB."""
    events = await wallet_repo.get_wallet_events_for_token(db, token_mint, event_type="BUY")

    buy_records: list[BuyRecord] = []
    for evt in events:
        score = await wallet_repo.get_wallet_score(db, evt.wallet_address)
        quality = score.wallet_quality if score else 50

        membership = await graph_repo.get_wallet_cluster_member(db, evt.wallet_address)

        cluster_id = str(membership.cluster_id) if membership else None
        cluster_type = None
        cluster_size = 1

        if membership:
            cluster_obj = await graph_repo.get_wallet_cluster(db, evt.wallet_address)
            if cluster_obj:
                cluster_type = cluster_obj.cluster_type
                cluster_size = await graph_repo.get_cluster_member_count(db, membership.cluster_id)

        buy_records.append(BuyRecord(
            wallet_address=evt.wallet_address,
            wallet_quality=quality,
            event_time=evt.event_time,
            cluster_id=cluster_id,
            cluster_type=cluster_type,
            cluster_size=cluster_size,
        ))

    return buy_records


async def detect_kol_already_called(token_mint: str, db: AsyncSession) -> bool:
    stmt = (
        select(func.count())
        .select_from(WalletEvent)
        .join(TrackedWallet, TrackedWallet.wallet_address == WalletEvent.wallet_address)
        .where(
            WalletEvent.token_mint == token_mint,
            WalletEvent.event_type == "BUY",
            TrackedWallet.wallet_type == "KOL_PRECALL",
        )
    )
    result = await db.execute(stmt)
    return bool(result.scalar_one())


async def is_copycat_mint(symbol: str | None, name: str | None, db: AsyncSession) -> bool:
    normalized_symbol = _normalize_token_text(symbol)
    normalized_name = _normalize_token_text(name)
    if not normalized_symbol and not normalized_name:
        return False
    if ((name or "").lower(), (symbol or "").lower()) in KNOWN_LEGITIMATE_TOKENS:
        return False

    stmt = select(CandidateToken.symbol, CandidateToken.name)
    result = await db.execute(stmt)
    for existing_symbol, existing_name in result.all():
        existing_symbol_norm = _normalize_token_text(existing_symbol)
        existing_name_norm = _normalize_token_text(existing_name)
        if normalized_symbol and existing_symbol_norm:
            if 0 < _levenshtein(normalized_symbol, existing_symbol_norm) < 2:
                return True
        if normalized_name and existing_name_norm:
            if 0 < _levenshtein(normalized_name, existing_name_norm) < 2:
                return True
    return False


async def has_social_drainer_link(social_posts: list[Any]) -> bool:
    for post in social_posts:
        if isinstance(post, dict):
            text = " ".join(str(post.get(key, "")) for key in ("text", "content", "title"))
        else:
            text = str(post)
        for pattern in MALICIOUS_PATTERNS:
            if pattern.search(text):
                return True
    return False


async def update_candidate_relationships(
    token_mint: str,
    wallet_address: str,
    event_time: datetime,
    db: AsyncSession,
) -> None:
    await graph_repo.add_wallet_token_edge(db, wallet_address, token_mint, event_time)


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
    existing_event = await wallet_repo.get_wallet_event_by_signature(db, event.tx_signature)
    if existing_event is not None:
        return None
    await wallet_repo.save_wallet_event(db, event)

    # ── 2. Upsert candidate token ────────────────────────────────────────
    candidate = await token_repo.upsert_candidate_token(
        db,
        event.token_mint,
        first_seen_at=datetime.utcnow(),
        status="ENRICHING",
    )

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
            None, None, False,
            jupiter.SellabilityReport(
                route_exists=False,
                price_impact_025_sol=None,
                price_impact_1_sol=None,
                price_impact_5_sol=None,
                all_quotes_succeeded=False,
            ),
        )

    concentration, mint_auth, freeze_auth, dev_dump, sell_report = risk_data
    sell_exists = sell_report.route_exists
    impact_025sol = sell_report.price_impact_025_sol
    impact_1sol = sell_report.price_impact_1_sol
    impact_5sol = sell_report.price_impact_5_sol
    kol_already_called = await detect_kol_already_called(event.token_mint, db)
    copycat_mint = await is_copycat_mint(candidate.symbol, candidate.name, db)
    social_drainer_link = await has_social_drainer_link(social_score.evidence.all_texts)

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
        kol_already_called=kol_already_called,
        dev_dump_detected=dev_dump,
        copycat_mint=copycat_mint,
        social_drainer_link=social_drainer_link,
    )

    # ── 6. Score components ──────────────────────────────────────────────
    market_score = score_market(market_ctx)
    wallet_score = min(100, int(
        0.70 * convergence.convergence_score
        + 0.30 * (buyers[0].wallet_quality if buyers else 50)
    ))
    history_score = await analyze_history(
        event.token_mint,
        candidate.creator_wallet,
        market_ctx.pool_age_minutes or 0.0,
        db,
        solana_rpc,
        helius,
    )
    execution_score_int = score_execution(sell_report, settings.max_price_impact_1_sol)

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
    await token_repo.save_market_snapshot(db, event.token_mint, market_ctx)
    await token_repo.save_risk_snapshot(
        db,
        event.token_mint,
        risk_report,
        concentration,
        mint_authority_active=mint_auth,
        freeze_authority_active=freeze_auth,
        sell_quote_exists=sell_exists,
        price_impact_025_sol=impact_025sol,
        price_impact_1_sol=impact_1sol,
        price_impact_5_sol=impact_5sol,
    )
    await token_repo.save_social_snapshot(db, event.token_mint, social_score)

    token_score = await token_repo.save_token_score(db, result, event.token_mint)
    await update_candidate_relationships(event.token_mint, event.wallet_address, event.event_time, db)

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
    AuditLedger.record_decision(
        token_mint=event.token_mint,
        decision=result.decision,
        total_score=result.total_score,
        score_breakdown={
            "wallet_score": result.wallet_score,
            "market_score": result.market_score,
            "risk_score": result.risk_score,
            "social_score": result.social_score,
            "history_score": result.history_score,
            "execution_score": result.execution_score,
        },
        convergence_wallets=convergence.independent_buyer_count,
        triggered_by_wallet=event.wallet_address,
    )

    return result
