"""Alert and outcome repository helpers."""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from wigs.models import Alert, TokenOutcome


async def save_alert(
    db: AsyncSession,
    token_mint: str,
    score_id,
    channel: str,
    decision: str,
    message: str,
    status: str,
) -> Alert:
    alert = Alert(
        token_mint=token_mint,
        score_id=score_id,
        channel=channel,
        decision=decision,
        message=message,
        delivery_status=status,
    )
    db.add(alert)
    await db.flush()
    return alert


async def list_unlabeled_alerts(db: AsyncSession) -> list[Alert]:
    stmt = (
        select(Alert)
        .join(TokenOutcome, Alert.id == TokenOutcome.alert_id, isouter=True)
        .where(TokenOutcome.id.is_(None))
        .order_by(desc(Alert.sent_at))
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_recent_labeled_alerts(db: AsyncSession, limit: int = 100) -> list[Alert]:
    stmt = (
        select(Alert)
        .join(TokenOutcome, Alert.id == TokenOutcome.alert_id)
        .order_by(desc(Alert.sent_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_recent_completed_outcomes(db: AsyncSession, limit: int = 100) -> list[TokenOutcome]:
    result = await db.execute(
        select(TokenOutcome)
        .where(
            TokenOutcome.measurement_complete.is_(True),
            TokenOutcome.label.is_not(None),
        )
        .order_by(desc(TokenOutcome.labeled_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def save_outcome(
    db: AsyncSession,
    token_mint: str,
    alert_id,
    label: str,
    **kwargs,
) -> TokenOutcome:
    outcome = TokenOutcome(
        token_mint=token_mint,
        alert_id=alert_id,
        label=label,
        **kwargs,
    )
    db.add(outcome)
    await db.flush()
    return outcome


async def get_outcome_for_alert(db: AsyncSession, alert_id) -> TokenOutcome | None:
    result = await db.execute(
        select(TokenOutcome).where(TokenOutcome.alert_id == alert_id)
    )
    return result.scalar_one_or_none()
