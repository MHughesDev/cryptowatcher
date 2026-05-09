"""SQLAlchemy ORM models for WIGS."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wigs.database import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def now_utc() -> datetime:
    return datetime.utcnow()


# ── Enums ─────────────────────────────────────────────────────────────────────

WALLET_TYPE = Enum(
    "SCOUT", "WHALE", "SMART_MONEY", "KOL_PRECALL", "DEV_ADJACENT", "UNKNOWN",
    name="wallet_type",
)
WALLET_LIFECYCLE = Enum(
    "DISCOVERED", "ACTIVE", "DEGRADED", "RETIRED",
    name="wallet_lifecycle",
)
CLUSTER_TYPE = Enum(
    "SMART_MONEY", "CABAL_SUSPECT", "DEV_SUSPECT", "BOT_FARM", "KOL_SUSPECT", "UNKNOWN",
    name="cluster_type",
)
EVENT_TYPE = Enum(
    "BUY", "SELL", "TRANSFER_IN", "TRANSFER_OUT", "LP_ADD", "LP_REMOVE",
    name="event_type",
)
CANDIDATE_STATUS = Enum(
    "PENDING", "ENRICHING", "WATCH", "STRONG_WATCH", "STRONG_CANDIDATE", "REJECTED",
    name="candidate_status",
)
LAUNCH_SOURCE = Enum(
    "PUMP_FUN", "PUMPSWAP", "RAYDIUM", "METEORA", "ORCA", "UNKNOWN",
    name="launch_source",
)
DECISION = Enum(
    "AVOID", "WATCH", "STRONG_WATCH", "STRONG_CANDIDATE",
    name="decision",
)
RISK_LEVEL = Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="risk_level")
ALERT_CHANNEL = Enum("TELEGRAM", "DISCORD", "EMAIL", "LOG", name="alert_channel")
DELIVERY_STATUS = Enum("SENT", "FAILED", "SKIPPED", name="delivery_status")
OUTCOME_LABEL = Enum(
    "RUG", "DEAD_ON_ARRIVAL", "ONE_CYCLE_PUMP", "TRADEABLE_RUNNER", "SURVIVOR", "HEAVY_HITTER",
    name="outcome_label",
)


# ── Wallet tables ─────────────────────────────────────────────────────────────

class TrackedWallet(Base):
    __tablename__ = "tracked_wallets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    wallet_address: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    wallet_type: Mapped[str] = mapped_column(WALLET_TYPE, nullable=False, default="UNKNOWN")
    lifecycle: Mapped[str] = mapped_column(WALLET_LIFECYCLE, nullable=False, default="DISCOVERED")
    label: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=now_utc, onupdate=now_utc
    )

    events: Mapped[list["WalletEvent"]] = relationship(back_populates="wallet_ref", lazy="select")
    scores: Mapped[list["WalletScoreSnapshot"]] = relationship(back_populates="wallet_ref", lazy="select")


class WalletEvent(Base):
    __tablename__ = "wallet_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    wallet_address: Mapped[str] = mapped_column(String(64), ForeignKey("tracked_wallets.wallet_address"), nullable=False, index=True)
    tx_signature: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    token_mint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(EVENT_TYPE, nullable=False)
    amount_sol: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount_token: Mapped[float | None] = mapped_column(Float, nullable=True)
    dex_or_program: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pool_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)
    detected_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    wallet_ref: Mapped["TrackedWallet"] = relationship(back_populates="events", lazy="select")

    __table_args__ = (
        Index("ix_wallet_events_wallet_time", "wallet_address", "event_time"),
        Index("ix_wallet_events_mint_time", "token_mint", "event_time"),
    )


class WalletScoreSnapshot(Base):
    __tablename__ = "wallet_score_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    wallet_address: Mapped[str] = mapped_column(String(64), ForeignKey("tracked_wallets.wallet_address"), nullable=False, index=True)
    realized_pnl_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    early_entry_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lead_lag_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exit_quality_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rug_avoidance_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repeatability_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    independence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    freshness_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wallet_quality: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc, index=True)

    wallet_ref: Mapped["TrackedWallet"] = relationship(back_populates="scores", lazy="select")

    __table_args__ = (
        Index("ix_wallet_scores_addr_time", "wallet_address", "captured_at"),
    )


class WalletBetaPosterior(Base):
    """Thompson Sampling Beta(alpha, beta) posterior per wallet."""

    __tablename__ = "wallet_beta_posteriors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    wallet_address: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    alpha: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)  # successes + prior
    beta: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)   # failures + prior
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc, onupdate=now_utc)


class WalletCluster(Base):
    __tablename__ = "wallet_clusters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    cluster_label: Mapped[str | None] = mapped_column(String(256), nullable=True)
    cluster_type: Mapped[str] = mapped_column(CLUSTER_TYPE, nullable=False, default="UNKNOWN")
    suspicion_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc, onupdate=now_utc)

    members: Mapped[list["WalletClusterMember"]] = relationship(back_populates="cluster", lazy="select")


class WalletClusterMember(Base):
    __tablename__ = "wallet_cluster_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    cluster_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wallet_clusters.id"), nullable=False)
    wallet_address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    membership_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)

    cluster: Mapped["WalletCluster"] = relationship(back_populates="members", lazy="select")

    __table_args__ = (UniqueConstraint("cluster_id", "wallet_address"),)


# ── Token tables ──────────────────────────────────────────────────────────────

class CandidateToken(Base):
    __tablename__ = "candidate_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    token_mint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    creator_wallet: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at_chain: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)
    launch_source: Mapped[str | None] = mapped_column(LAUNCH_SOURCE, nullable=True)
    status: Mapped[str] = mapped_column(CANDIDATE_STATUS, nullable=False, default="PENDING")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc, onupdate=now_utc)


class TokenPool(Base):
    __tablename__ = "token_pools"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    token_mint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    pool_address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dex: Mapped[str] = mapped_column(String(64), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at_chain: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)

    __table_args__ = (UniqueConstraint("token_mint", "pool_address"),)


class TokenMarketSnapshot(Base):
    __tablename__ = "token_market_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    token_mint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    price_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    fdv: Mapped[float | None] = mapped_column(Float, nullable=True)
    liquidity_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    volume_5m: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    buyers_5m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sellers_5m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buy_sell_ratio_5m: Mapped[float | None] = mapped_column(Float, nullable=True)
    unique_buyers_5m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_trade_size_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    pool_age_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    primary_pool_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc, index=True)

    __table_args__ = (
        Index("ix_market_snap_mint_time", "token_mint", "captured_at"),
    )


class TokenRiskSnapshot(Base):
    __tablename__ = "token_risk_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    token_mint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mint_authority_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    freeze_authority_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    top_10_holder_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    top_20_holder_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    dev_holding_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    gini_coefficient: Mapped[float | None] = mapped_column(Float, nullable=True)
    hhi: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_quote_exists: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    price_impact_025_sol: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_impact_1_sol: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_impact_5_sol: Mapped[float | None] = mapped_column(Float, nullable=True)
    liquidity_drop_pct_15m: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_flags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc, index=True)

    __table_args__ = (
        Index("ix_risk_snap_mint_time", "token_mint", "captured_at"),
    )


class SocialSnapshot(Base):
    __tablename__ = "social_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    token_mint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reddit_mentions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    telegram_mentions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discord_mentions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    youtube_mentions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gdelt_mentions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    velocity_acceleration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    novelty_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    organic_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    social_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc, index=True)

    __table_args__ = (
        Index("ix_social_snap_mint_time", "token_mint", "captured_at"),
    )


class TokenScore(Base):
    __tablename__ = "token_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    token_mint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    wallet_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    market_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    social_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    history_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    convergence_independent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    convergence_time_spread_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_adjustment: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    decision: Mapped[str] = mapped_column(DECISION, nullable=False, default="AVOID")
    risk_level: Mapped[str] = mapped_column(RISK_LEVEL, nullable=False, default="HIGH")
    score_reasons: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc, index=True)

    __table_args__ = (
        Index("ix_token_scores_mint_time", "token_mint", "created_at"),
    )


# ── Alert tables ──────────────────────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    token_mint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    score_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("token_scores.id"), nullable=True)
    channel: Mapped[str] = mapped_column(ALERT_CHANNEL, nullable=False)
    decision: Mapped[str] = mapped_column(DECISION, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)
    delivery_status: Mapped[str] = mapped_column(DELIVERY_STATUS, nullable=False, default="SENT")


class TokenOutcome(Base):
    __tablename__ = "token_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    token_mint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    alert_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=True)
    label: Mapped[str | None] = mapped_column(OUTCOME_LABEL, nullable=True)
    max_return_5m: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_return_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_return_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    tradable_return_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_liquidity_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    measurement_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    labeled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc)

    __table_args__ = (
        Index("ix_outcomes_mint_time", "token_mint", "labeled_at"),
    )
