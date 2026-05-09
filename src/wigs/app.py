"""FastAPI application — webhook receiver and REST API."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from wigs.config import get_settings
from wigs.database import get_db
from wigs.models import Alert, CandidateToken, TokenScore, TrackedWallet, WalletScoreSnapshot
from wigs.pipeline import handle_wallet_event

log = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="WIGS — Wallet Intelligence Graph Scanner",
    version="0.1.0",
    description="Solana memecoin alpha detection via wallet convergence scoring.",
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Helius webhook receiver ───────────────────────────────────────────────────

@app.post("/webhook/helius")
async def helius_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_helius_signature: str | None = Header(default=None),
) -> JSONResponse:
    body = await request.body()

    # Verify HMAC signature
    if settings.helius_webhook_secret:
        if not x_helius_signature:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")
        expected = hmac.new(
            settings.helius_webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, x_helius_signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    payload: list[dict[str, Any]] = await request.json()
    if not isinstance(payload, list):
        payload = [payload]

    processed = 0
    for event in payload:
        # Identify which tracked wallet triggered this event
        account_data = event.get("accountData", [])
        wallet_address = event.get("feePayer")  # fallback
        for acct in account_data:
            if acct.get("account") and acct.get("nativeBalanceChange", 0) < 0:
                wallet_address = acct["account"]
                break

        if not wallet_address:
            continue

        # Only process events from tracked wallets
        tracked = await db.execute(
            select(TrackedWallet).where(
                TrackedWallet.wallet_address == wallet_address,
                TrackedWallet.is_active.is_(True),
            )
        )
        if not tracked.scalar_one_or_none():
            continue

        result = await handle_wallet_event(event, wallet_address, db)
        if result:
            processed += 1

    return JSONResponse({"processed": processed})


# ── Candidate endpoints ───────────────────────────────────────────────────────

@app.get("/candidates")
async def list_candidates(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 20,
    decision: str | None = None,
) -> list[dict[str, Any]]:
    stmt = (
        select(CandidateToken, TokenScore)
        .join(TokenScore, CandidateToken.token_mint == TokenScore.token_mint, isouter=True)
        .order_by(desc(TokenScore.created_at))
        .limit(limit)
    )
    if decision:
        stmt = stmt.where(TokenScore.decision == decision.upper())

    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "token_mint": token.token_mint,
            "symbol": token.symbol,
            "name": token.name,
            "status": token.status,
            "first_seen_at": token.first_seen_at.isoformat() if token.first_seen_at else None,
            "score": {
                "total": score.total_score if score else None,
                "decision": score.decision if score else None,
                "wallet": score.wallet_score if score else None,
                "market": score.market_score if score else None,
                "risk": score.risk_score if score else None,
                "social": score.social_score if score else None,
                "convergence_wallets": score.convergence_independent_count if score else 0,
                "convergence_spread_s": score.convergence_time_spread_s if score else None,
            } if score else None,
        }
        for token, score in rows
    ]


@app.get("/candidates/{token_mint}")
async def get_candidate(
    token_mint: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    token_result = await db.execute(
        select(CandidateToken).where(CandidateToken.token_mint == token_mint)
    )
    token = token_result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    score_result = await db.execute(
        select(TokenScore)
        .where(TokenScore.token_mint == token_mint)
        .order_by(desc(TokenScore.created_at))
        .limit(1)
    )
    score = score_result.scalar_one_or_none()

    return {
        "token_mint": token.token_mint,
        "symbol": token.symbol,
        "name": token.name,
        "creator_wallet": token.creator_wallet,
        "launch_source": token.launch_source,
        "status": token.status,
        "first_seen_at": token.first_seen_at.isoformat() if token.first_seen_at else None,
        "score": {
            "total": score.total_score,
            "decision": score.decision,
            "risk_level": score.risk_level,
            "wallet": score.wallet_score,
            "market": score.market_score,
            "risk": score.risk_score,
            "social": score.social_score,
            "history": score.history_score,
            "execution": score.execution_score,
            "convergence_wallets": score.convergence_independent_count,
            "convergence_spread_s": score.convergence_time_spread_s,
            "threshold_adjustment": score.threshold_adjustment,
            "reasons": score.score_reasons,
            "scored_at": score.created_at.isoformat() if score.created_at else None,
        } if score else None,
    }


# ── Wallet endpoints ──────────────────────────────────────────────────────────

@app.get("/wallets")
async def list_wallets(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    lifecycle: str | None = None,
) -> list[dict[str, Any]]:
    stmt = select(TrackedWallet).order_by(desc(TrackedWallet.updated_at)).limit(limit)
    if lifecycle:
        stmt = stmt.where(TrackedWallet.lifecycle == lifecycle.upper())

    result = await db.execute(stmt)
    wallets = result.scalars().all()

    return [
        {
            "wallet_address": w.wallet_address,
            "label": w.label,
            "wallet_type": w.wallet_type,
            "lifecycle": w.lifecycle,
            "source": w.source,
            "is_active": w.is_active,
        }
        for w in wallets
    ]


@app.get("/wallets/{address}")
async def get_wallet(
    address: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    wallet_result = await db.execute(
        select(TrackedWallet).where(TrackedWallet.wallet_address == address)
    )
    wallet = wallet_result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    score_result = await db.execute(
        select(WalletScoreSnapshot)
        .where(WalletScoreSnapshot.wallet_address == address)
        .order_by(desc(WalletScoreSnapshot.captured_at))
        .limit(1)
    )
    score = score_result.scalar_one_or_none()

    return {
        "wallet_address": wallet.wallet_address,
        "label": wallet.label,
        "wallet_type": wallet.wallet_type,
        "lifecycle": wallet.lifecycle,
        "source": wallet.source,
        "is_active": wallet.is_active,
        "score": {
            "wallet_quality": score.wallet_quality,
            "realized_pnl": score.realized_pnl_score,
            "early_entry": score.early_entry_score,
            "lead_lag": score.lead_lag_score,
            "exit_quality": score.exit_quality_score,
            "rug_avoidance": score.rug_avoidance_score,
            "repeatability": score.repeatability_score,
            "independence": score.independence_score,
            "freshness": score.freshness_score,
            "scored_at": score.captured_at.isoformat() if score.captured_at else None,
        } if score else None,
    }


# ── Alert history ─────────────────────────────────────────────────────────────

@app.get("/alerts")
async def list_alerts(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 30,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Alert).order_by(desc(Alert.sent_at)).limit(limit)
    )
    alerts = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "token_mint": a.token_mint,
            "decision": a.decision,
            "channel": a.channel,
            "delivery_status": a.delivery_status,
            "sent_at": a.sent_at.isoformat(),
        }
        for a in alerts
    ]
