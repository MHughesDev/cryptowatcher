"""Wallet-oriented repository helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from wigs.models import (
    TrackedWallet,
    WalletBetaPosterior,
    WalletEvent,
    WalletOutcomeApplication,
    WalletScoreSnapshot,
)


async def upsert_tracked_wallet(
    db: AsyncSession,
    address: str,
    label: str | None = None,
    *,
    source: str = "manual",
    wallet_type: str = "UNKNOWN",
) -> TrackedWallet:
    result = await db.execute(
        select(TrackedWallet).where(TrackedWallet.wallet_address == address)
    )
    wallet = result.scalar_one_or_none()
    if wallet is None:
        wallet = TrackedWallet(
            wallet_address=address,
            label=label,
            source=source,
            wallet_type=wallet_type,
            is_active=True,
        )
        db.add(wallet)
    else:
        if label is not None:
            wallet.label = label
        wallet.source = source or wallet.source
        wallet.wallet_type = wallet_type or wallet.wallet_type
        wallet.is_active = True
    await db.flush()
    return wallet


async def list_active_wallets(db: AsyncSession) -> list[TrackedWallet]:
    result = await db.execute(
        select(TrackedWallet).where(TrackedWallet.is_active.is_(True))
    )
    return list(result.scalars().all())


async def get_tracked_wallet(db: AsyncSession, address: str) -> TrackedWallet | None:
    result = await db.execute(
        select(TrackedWallet).where(TrackedWallet.wallet_address == address)
    )
    return result.scalar_one_or_none()


async def save_wallet_event(db: AsyncSession, event: Any) -> WalletEvent:
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
    await db.flush()
    return db_event


async def get_wallet_event_by_signature(db: AsyncSession, tx_signature: str) -> WalletEvent | None:
    result = await db.execute(
        select(WalletEvent).where(WalletEvent.tx_signature == tx_signature)
    )
    return result.scalar_one_or_none()


async def get_wallet_events_for_token(
    db: AsyncSession,
    token_mint: str,
    event_type: str = "BUY",
) -> list[WalletEvent]:
    result = await db.execute(
        select(WalletEvent)
        .where(
            WalletEvent.token_mint == token_mint,
            WalletEvent.event_type == event_type,
        )
        .order_by(WalletEvent.event_time.asc())
    )
    return list(result.scalars().all())


async def get_recent_wallet_events(
    db: AsyncSession,
    wallet_address: str,
    limit: int = 100,
) -> list[WalletEvent]:
    result = await db.execute(
        select(WalletEvent)
        .where(WalletEvent.wallet_address == wallet_address)
        .order_by(desc(WalletEvent.event_time))
        .limit(limit)
    )
    return list(result.scalars().all())


async def save_wallet_score(
    db: AsyncSession,
    address: str,
    scores: dict[str, Any],
) -> WalletScoreSnapshot:
    snapshot = WalletScoreSnapshot(
        wallet_address=address,
        realized_pnl_score=int(scores.get("realized_pnl_score", 0)),
        early_entry_score=int(scores.get("early_entry_score", 0)),
        lead_lag_score=int(scores.get("lead_lag_score", 0)),
        exit_quality_score=int(scores.get("exit_quality_score", 0)),
        rug_avoidance_score=int(scores.get("rug_avoidance_score", 0)),
        repeatability_score=int(scores.get("repeatability_score", 0)),
        independence_score=int(scores.get("independence_score", 0)),
        freshness_score=int(scores.get("freshness_score", 0)),
        wallet_quality=int(scores.get("wallet_quality", 0)),
    )
    db.add(snapshot)
    await db.flush()
    return snapshot


async def get_wallet_score(db: AsyncSession, address: str) -> WalletScoreSnapshot | None:
    result = await db.execute(
        select(WalletScoreSnapshot)
        .where(WalletScoreSnapshot.wallet_address == address)
        .order_by(desc(WalletScoreSnapshot.captured_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def save_wallet_beta_posterior(
    db: AsyncSession,
    address: str,
    alpha: float,
    beta: float,
) -> WalletBetaPosterior:
    posterior = await get_wallet_beta_posterior(db, address)
    if posterior is None:
        posterior = WalletBetaPosterior(wallet_address=address, alpha=alpha, beta=beta)
        db.add(posterior)
    else:
        posterior.alpha = alpha
        posterior.beta = beta
    await db.flush()
    return posterior


async def get_wallet_beta_posterior(
    db: AsyncSession,
    address: str,
) -> WalletBetaPosterior | None:
    result = await db.execute(
        select(WalletBetaPosterior).where(WalletBetaPosterior.wallet_address == address)
    )
    return result.scalar_one_or_none()


async def has_wallet_outcome_application(
    db: AsyncSession,
    wallet_address: str,
    token_outcome_id,
) -> bool:
    result = await db.execute(
        select(WalletOutcomeApplication.id).where(
            WalletOutcomeApplication.wallet_address == wallet_address,
            WalletOutcomeApplication.token_outcome_id == token_outcome_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def save_wallet_outcome_application(
    db: AsyncSession,
    wallet_address: str,
    token_outcome_id,
    token_mint: str,
) -> WalletOutcomeApplication:
    application = WalletOutcomeApplication(
        wallet_address=wallet_address,
        token_outcome_id=token_outcome_id,
        token_mint=token_mint,
    )
    db.add(application)
    await db.flush()
    return application


async def claim_wallet_outcome_application(
    db: AsyncSession,
    wallet_address: str,
    token_outcome_id,
    token_mint: str,
) -> bool:
    stmt = (
        insert(WalletOutcomeApplication)
        .values(
            wallet_address=wallet_address,
            token_outcome_id=token_outcome_id,
            token_mint=token_mint,
        )
        .on_conflict_do_nothing(
            index_elements=["wallet_address", "token_outcome_id"],
        )
        .returning(WalletOutcomeApplication.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None
