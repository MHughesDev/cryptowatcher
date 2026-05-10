"""Graph-oriented repository helpers built on existing event and cluster tables."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from wigs.models import WalletCluster, WalletClusterMember, WalletEvent


async def add_wallet_token_edge(
    db: AsyncSession,
    wallet: str,
    token_mint: str,
    event_time: datetime,
) -> None:
    existing = await db.execute(
        select(WalletEvent).where(
            WalletEvent.wallet_address == wallet,
            WalletEvent.token_mint == token_mint,
            WalletEvent.event_time == event_time,
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(
            WalletEvent(
                wallet_address=wallet,
                tx_signature=f"synthetic:{wallet}:{token_mint}:{int(event_time.timestamp())}",
                token_mint=token_mint,
                event_type="BUY",
                event_time=event_time,
                raw_payload={"synthetic_edge": True},
            )
        )
        await db.flush()


async def add_wallet_wallet_edge(
    db: AsyncSession,
    wallet_a: str,
    wallet_b: str,
    edge_type: str,
) -> None:
    wallets = sorted({wallet_a, wallet_b})
    label = f"edge:{edge_type}:{wallets[0]}:{wallets[1]}"
    existing = await db.execute(
        select(WalletCluster).where(WalletCluster.cluster_label == label)
    )
    cluster = existing.scalar_one_or_none()
    if cluster is None:
        cluster = WalletCluster(
            cluster_label=label,
            cluster_type="UNKNOWN",
            suspicion_score=0.0,
            confidence=0.0,
        )
        db.add(cluster)
        await db.flush()

    current = await get_cluster_members(db, cluster.id)
    for wallet in wallets:
        if wallet not in current:
            db.add(
                WalletClusterMember(
                    cluster_id=cluster.id,
                    wallet_address=wallet,
                    membership_reason=edge_type,
                    confidence=0.0,
                )
            )
    await db.flush()


async def get_wallet_cluster(db: AsyncSession, wallet: str) -> WalletCluster | None:
    result = await db.execute(
        select(WalletCluster)
        .join(WalletClusterMember, WalletClusterMember.cluster_id == WalletCluster.id)
        .where(WalletClusterMember.wallet_address == wallet)
        .order_by(desc(WalletCluster.updated_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_wallet_cluster_member(db: AsyncSession, wallet: str) -> WalletClusterMember | None:
    result = await db.execute(
        select(WalletClusterMember).where(WalletClusterMember.wallet_address == wallet)
    )
    return result.scalar_one_or_none()


async def get_cluster_members(db: AsyncSession, cluster_id) -> list[str]:
    result = await db.execute(
        select(WalletClusterMember.wallet_address).where(
            WalletClusterMember.cluster_id == cluster_id
        )
    )
    return list(result.scalars().all())


async def get_cluster_member_count(db: AsyncSession, cluster_id) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(WalletClusterMember)
        .where(WalletClusterMember.cluster_id == cluster_id)
    )
    return int(result.scalar_one())


async def save_cluster(
    db: AsyncSession,
    cluster_type: str,
    member_addresses: list[str],
    suspicion_score: float,
) -> WalletCluster:
    cluster = WalletCluster(
        cluster_type=cluster_type,
        suspicion_score=suspicion_score,
        confidence=min(1.0, max(0.0, suspicion_score)),
    )
    db.add(cluster)
    await db.flush()
    for address in sorted(set(member_addresses)):
        db.add(
            WalletClusterMember(
                cluster_id=cluster.id,
                wallet_address=address,
                membership_reason="save_cluster",
                confidence=min(1.0, max(0.0, suspicion_score)),
            )
        )
    await db.flush()
    return cluster


async def get_wallets_that_bought_token(db: AsyncSession, token_mint: str) -> list[str]:
    result = await db.execute(
        select(WalletEvent.wallet_address)
        .where(
            WalletEvent.token_mint == token_mint,
            WalletEvent.event_type == "BUY",
        )
        .distinct()
    )
    return list(result.scalars().all())


async def get_copurchase_pairs(
    db: AsyncSession,
    min_shared_tokens: int = 2,
) -> list[tuple[str, str, int]]:
    w1 = WalletEvent.__table__.alias("w1")
    w2 = WalletEvent.__table__.alias("w2")
    stmt = (
        select(
            w1.c.wallet_address,
            w2.c.wallet_address,
            func.count(func.distinct(w1.c.token_mint)).label("shared_count"),
        )
        .where(
            and_(
                w1.c.event_type == "BUY",
                w2.c.event_type == "BUY",
                w1.c.token_mint == w2.c.token_mint,
                w1.c.wallet_address < w2.c.wallet_address,
            )
        )
        .group_by(w1.c.wallet_address, w2.c.wallet_address)
        .having(func.count(func.distinct(w1.c.token_mint)) >= min_shared_tokens)
    )
    result = await db.execute(stmt)
    return [
        (wallet_a, wallet_b, int(shared_count))
        for wallet_a, wallet_b, shared_count in result.all()
    ]
