"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-05-09 17:05:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


wallet_type_enum = postgresql.ENUM(
    "SCOUT",
    "WHALE",
    "SMART_MONEY",
    "KOL_PRECALL",
    "DEV_ADJACENT",
    "UNKNOWN",
    name="wallet_type",
)
wallet_lifecycle_enum = postgresql.ENUM(
    "DISCOVERED",
    "ACTIVE",
    "DEGRADED",
    "RETIRED",
    name="wallet_lifecycle",
)
cluster_type_enum = postgresql.ENUM(
    "SMART_MONEY",
    "CABAL_SUSPECT",
    "DEV_SUSPECT",
    "BOT_FARM",
    "KOL_SUSPECT",
    "UNKNOWN",
    name="cluster_type",
)
event_type_enum = postgresql.ENUM(
    "BUY",
    "SELL",
    "TRANSFER_IN",
    "TRANSFER_OUT",
    "LP_ADD",
    "LP_REMOVE",
    name="event_type",
)
candidate_status_enum = postgresql.ENUM(
    "PENDING",
    "ENRICHING",
    "WATCH",
    "STRONG_WATCH",
    "STRONG_CANDIDATE",
    "REJECTED",
    name="candidate_status",
)
launch_source_enum = postgresql.ENUM(
    "PUMP_FUN",
    "PUMPSWAP",
    "RAYDIUM",
    "METEORA",
    "ORCA",
    "UNKNOWN",
    name="launch_source",
)
decision_enum = postgresql.ENUM(
    "AVOID",
    "WATCH",
    "STRONG_WATCH",
    "STRONG_CANDIDATE",
    name="decision",
)
risk_level_enum = postgresql.ENUM("LOW", "MEDIUM", "HIGH", "CRITICAL", name="risk_level")
alert_channel_enum = postgresql.ENUM(
    "TELEGRAM",
    "DISCORD",
    "EMAIL",
    "LOG",
    name="alert_channel",
)
delivery_status_enum = postgresql.ENUM(
    "SENT",
    "FAILED",
    "SKIPPED",
    name="delivery_status",
)
outcome_label_enum = postgresql.ENUM(
    "RUG",
    "DEAD_ON_ARRIVAL",
    "ONE_CYCLE_PUMP",
    "TRADEABLE_RUNNER",
    "SURVIVOR",
    "HEAVY_HITTER",
    name="outcome_label",
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (
        wallet_type_enum,
        wallet_lifecycle_enum,
        cluster_type_enum,
        event_type_enum,
        candidate_status_enum,
        launch_source_enum,
        decision_enum,
        risk_level_enum,
        alert_channel_enum,
        delivery_status_enum,
        outcome_label_enum,
    ):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "tracked_wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("wallet_type", wallet_type_enum, nullable=False),
        sa.Column("lifecycle", wallet_lifecycle_enum, nullable=False),
        sa.Column("label", sa.String(length=256), nullable=True),
        sa.Column("source", sa.String(length=256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wallet_address"),
    )
    op.create_index(
        op.f("ix_tracked_wallets_wallet_address"),
        "tracked_wallets",
        ["wallet_address"],
        unique=False,
    )

    op.create_table(
        "wallet_beta_posteriors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("alpha", sa.Float(), nullable=False),
        sa.Column("beta", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wallet_address"),
    )
    op.create_index(
        op.f("ix_wallet_beta_posteriors_wallet_address"),
        "wallet_beta_posteriors",
        ["wallet_address"],
        unique=False,
    )

    op.create_table(
        "wallet_clusters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cluster_label", sa.String(length=256), nullable=True),
        sa.Column("cluster_type", cluster_type_enum, nullable=False),
        sa.Column("suspicion_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "candidate_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_mint", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("creator_wallet", sa.String(length=64), nullable=True),
        sa.Column("created_at_chain", sa.DateTime(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("launch_source", launch_source_enum, nullable=True),
        sa.Column("status", candidate_status_enum, nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_mint"),
    )
    op.create_index(
        op.f("ix_candidate_tokens_token_mint"),
        "candidate_tokens",
        ["token_mint"],
        unique=False,
    )

    op.create_table(
        "wallet_cluster_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cluster_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("membership_reason", sa.String(length=512), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["cluster_id"], ["wallet_clusters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cluster_id", "wallet_address"),
    )
    op.create_index(
        op.f("ix_wallet_cluster_members_wallet_address"),
        "wallet_cluster_members",
        ["wallet_address"],
        unique=False,
    )

    op.create_table(
        "wallet_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("tx_signature", sa.String(length=128), nullable=False),
        sa.Column("token_mint", sa.String(length=64), nullable=True),
        sa.Column("event_type", event_type_enum, nullable=False),
        sa.Column("amount_sol", sa.Float(), nullable=True),
        sa.Column("amount_usd", sa.Float(), nullable=True),
        sa.Column("amount_token", sa.Float(), nullable=True),
        sa.Column("dex_or_program", sa.String(length=128), nullable=True),
        sa.Column("pool_address", sa.String(length=64), nullable=True),
        sa.Column("event_time", sa.DateTime(), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("detected_latency_ms", sa.Integer(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["wallet_address"], ["tracked_wallets.wallet_address"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tx_signature"),
    )
    op.create_index(op.f("ix_wallet_events_event_time"), "wallet_events", ["event_time"], unique=False)
    op.create_index(op.f("ix_wallet_events_token_mint"), "wallet_events", ["token_mint"], unique=False)
    op.create_index(
        op.f("ix_wallet_events_tx_signature"),
        "wallet_events",
        ["tx_signature"],
        unique=False,
    )
    op.create_index(
        op.f("ix_wallet_events_wallet_address"),
        "wallet_events",
        ["wallet_address"],
        unique=False,
    )
    op.create_index(
        "ix_wallet_events_mint_time",
        "wallet_events",
        ["token_mint", "event_time"],
        unique=False,
    )
    op.create_index(
        "ix_wallet_events_wallet_time",
        "wallet_events",
        ["wallet_address", "event_time"],
        unique=False,
    )

    op.create_table(
        "wallet_score_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("realized_pnl_score", sa.Integer(), nullable=False),
        sa.Column("early_entry_score", sa.Integer(), nullable=False),
        sa.Column("lead_lag_score", sa.Integer(), nullable=False),
        sa.Column("exit_quality_score", sa.Integer(), nullable=False),
        sa.Column("rug_avoidance_score", sa.Integer(), nullable=False),
        sa.Column("repeatability_score", sa.Integer(), nullable=False),
        sa.Column("independence_score", sa.Integer(), nullable=False),
        sa.Column("freshness_score", sa.Integer(), nullable=False),
        sa.Column("wallet_quality", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["wallet_address"], ["tracked_wallets.wallet_address"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_wallet_score_snapshots_captured_at"),
        "wallet_score_snapshots",
        ["captured_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_wallet_score_snapshots_wallet_address"),
        "wallet_score_snapshots",
        ["wallet_address"],
        unique=False,
    )
    op.create_index(
        "ix_wallet_scores_addr_time",
        "wallet_score_snapshots",
        ["wallet_address", "captured_at"],
        unique=False,
    )

    op.create_table(
        "token_pools",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_mint", sa.String(length=64), nullable=False),
        sa.Column("pool_address", sa.String(length=64), nullable=False),
        sa.Column("dex", sa.String(length=64), nullable=False),
        sa.Column("quote_asset", sa.String(length=16), nullable=False),
        sa.Column("created_at_chain", sa.DateTime(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_mint", "pool_address"),
    )
    op.create_index(op.f("ix_token_pools_pool_address"), "token_pools", ["pool_address"], unique=False)
    op.create_index(op.f("ix_token_pools_token_mint"), "token_pools", ["token_mint"], unique=False)

    op.create_table(
        "token_market_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_mint", sa.String(length=64), nullable=False),
        sa.Column("price_usd", sa.Float(), nullable=True),
        sa.Column("market_cap", sa.Float(), nullable=True),
        sa.Column("fdv", sa.Float(), nullable=True),
        sa.Column("liquidity_usd", sa.Float(), nullable=False),
        sa.Column("volume_5m", sa.Float(), nullable=True),
        sa.Column("volume_1h", sa.Float(), nullable=True),
        sa.Column("volume_24h", sa.Float(), nullable=True),
        sa.Column("buyers_5m", sa.Integer(), nullable=True),
        sa.Column("sellers_5m", sa.Integer(), nullable=True),
        sa.Column("buy_sell_ratio_5m", sa.Float(), nullable=True),
        sa.Column("unique_buyers_5m", sa.Integer(), nullable=True),
        sa.Column("avg_trade_size_usd", sa.Float(), nullable=True),
        sa.Column("pool_age_minutes", sa.Float(), nullable=True),
        sa.Column("primary_pool_address", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_token_market_snapshots_captured_at"),
        "token_market_snapshots",
        ["captured_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_token_market_snapshots_token_mint"),
        "token_market_snapshots",
        ["token_mint"],
        unique=False,
    )
    op.create_index(
        "ix_market_snap_mint_time",
        "token_market_snapshots",
        ["token_mint", "captured_at"],
        unique=False,
    )

    op.create_table(
        "token_risk_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_mint", sa.String(length=64), nullable=False),
        sa.Column("mint_authority_active", sa.Boolean(), nullable=True),
        sa.Column("freeze_authority_active", sa.Boolean(), nullable=True),
        sa.Column("top_10_holder_pct", sa.Float(), nullable=True),
        sa.Column("top_20_holder_pct", sa.Float(), nullable=True),
        sa.Column("dev_holding_pct", sa.Float(), nullable=True),
        sa.Column("gini_coefficient", sa.Float(), nullable=True),
        sa.Column("hhi", sa.Float(), nullable=True),
        sa.Column("sell_quote_exists", sa.Boolean(), nullable=False),
        sa.Column("price_impact_025_sol", sa.Float(), nullable=True),
        sa.Column("price_impact_1_sol", sa.Float(), nullable=True),
        sa.Column("price_impact_5_sol", sa.Float(), nullable=True),
        sa.Column("liquidity_drop_pct_15m", sa.Float(), nullable=True),
        sa.Column("risk_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_token_risk_snapshots_captured_at"),
        "token_risk_snapshots",
        ["captured_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_token_risk_snapshots_token_mint"),
        "token_risk_snapshots",
        ["token_mint"],
        unique=False,
    )
    op.create_index(
        "ix_risk_snap_mint_time",
        "token_risk_snapshots",
        ["token_mint", "captured_at"],
        unique=False,
    )

    op.create_table(
        "social_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_mint", sa.String(length=64), nullable=False),
        sa.Column("reddit_mentions", sa.Integer(), nullable=False),
        sa.Column("telegram_mentions", sa.Integer(), nullable=False),
        sa.Column("discord_mentions", sa.Integer(), nullable=False),
        sa.Column("youtube_mentions", sa.Integer(), nullable=False),
        sa.Column("gdelt_mentions", sa.Integer(), nullable=False),
        sa.Column("unique_sources", sa.Integer(), nullable=False),
        sa.Column("velocity_acceleration", sa.Float(), nullable=False),
        sa.Column("novelty_score", sa.Float(), nullable=False),
        sa.Column("organic_ratio", sa.Float(), nullable=True),
        sa.Column("social_score", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_social_snapshots_captured_at"),
        "social_snapshots",
        ["captured_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_social_snapshots_token_mint"),
        "social_snapshots",
        ["token_mint"],
        unique=False,
    )
    op.create_index(
        "ix_social_snap_mint_time",
        "social_snapshots",
        ["token_mint", "captured_at"],
        unique=False,
    )

    op.create_table(
        "token_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_mint", sa.String(length=64), nullable=False),
        sa.Column("wallet_score", sa.Integer(), nullable=False),
        sa.Column("market_score", sa.Integer(), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("social_score", sa.Integer(), nullable=False),
        sa.Column("history_score", sa.Integer(), nullable=False),
        sa.Column("execution_score", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False),
        sa.Column("convergence_independent_count", sa.Integer(), nullable=False),
        sa.Column("convergence_time_spread_s", sa.Float(), nullable=True),
        sa.Column("threshold_adjustment", sa.Integer(), nullable=False),
        sa.Column("decision", decision_enum, nullable=False),
        sa.Column("risk_level", risk_level_enum, nullable=False),
        sa.Column("score_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_token_scores_created_at"), "token_scores", ["created_at"], unique=False)
    op.create_index(op.f("ix_token_scores_token_mint"), "token_scores", ["token_mint"], unique=False)
    op.create_index(
        "ix_token_scores_mint_time",
        "token_scores",
        ["token_mint", "created_at"],
        unique=False,
    )

    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_mint", sa.String(length=64), nullable=False),
        sa.Column("score_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("channel", alert_channel_enum, nullable=False),
        sa.Column("decision", decision_enum, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("delivery_status", delivery_status_enum, nullable=False),
        sa.ForeignKeyConstraint(["score_id"], ["token_scores.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alerts_token_mint"), "alerts", ["token_mint"], unique=False)

    op.create_table(
        "token_outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_mint", sa.String(length=64), nullable=False),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("label", outcome_label_enum, nullable=True),
        sa.Column("max_return_5m", sa.Float(), nullable=True),
        sa.Column("max_return_1h", sa.Float(), nullable=True),
        sa.Column("max_return_24h", sa.Float(), nullable=True),
        sa.Column("tradable_return_1h", sa.Float(), nullable=True),
        sa.Column("max_drawdown_24h", sa.Float(), nullable=True),
        sa.Column("exit_liquidity_success", sa.Boolean(), nullable=True),
        sa.Column("measurement_complete", sa.Boolean(), nullable=False),
        sa.Column("labeled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_token_outcomes_token_mint"), "token_outcomes", ["token_mint"], unique=False)
    op.create_index(
        "ix_outcomes_mint_time",
        "token_outcomes",
        ["token_mint", "labeled_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_outcomes_mint_time", table_name="token_outcomes")
    op.drop_index(op.f("ix_token_outcomes_token_mint"), table_name="token_outcomes")
    op.drop_table("token_outcomes")

    op.drop_index(op.f("ix_alerts_token_mint"), table_name="alerts")
    op.drop_table("alerts")

    op.drop_index("ix_token_scores_mint_time", table_name="token_scores")
    op.drop_index(op.f("ix_token_scores_token_mint"), table_name="token_scores")
    op.drop_index(op.f("ix_token_scores_created_at"), table_name="token_scores")
    op.drop_table("token_scores")

    op.drop_index("ix_social_snap_mint_time", table_name="social_snapshots")
    op.drop_index(op.f("ix_social_snapshots_token_mint"), table_name="social_snapshots")
    op.drop_index(op.f("ix_social_snapshots_captured_at"), table_name="social_snapshots")
    op.drop_table("social_snapshots")

    op.drop_index("ix_risk_snap_mint_time", table_name="token_risk_snapshots")
    op.drop_index(op.f("ix_token_risk_snapshots_token_mint"), table_name="token_risk_snapshots")
    op.drop_index(op.f("ix_token_risk_snapshots_captured_at"), table_name="token_risk_snapshots")
    op.drop_table("token_risk_snapshots")

    op.drop_index("ix_market_snap_mint_time", table_name="token_market_snapshots")
    op.drop_index(op.f("ix_token_market_snapshots_token_mint"), table_name="token_market_snapshots")
    op.drop_index(op.f("ix_token_market_snapshots_captured_at"), table_name="token_market_snapshots")
    op.drop_table("token_market_snapshots")

    op.drop_index(op.f("ix_token_pools_token_mint"), table_name="token_pools")
    op.drop_index(op.f("ix_token_pools_pool_address"), table_name="token_pools")
    op.drop_table("token_pools")

    op.drop_index("ix_wallet_scores_addr_time", table_name="wallet_score_snapshots")
    op.drop_index(op.f("ix_wallet_score_snapshots_wallet_address"), table_name="wallet_score_snapshots")
    op.drop_index(op.f("ix_wallet_score_snapshots_captured_at"), table_name="wallet_score_snapshots")
    op.drop_table("wallet_score_snapshots")

    op.drop_index("ix_wallet_events_wallet_time", table_name="wallet_events")
    op.drop_index("ix_wallet_events_mint_time", table_name="wallet_events")
    op.drop_index(op.f("ix_wallet_events_wallet_address"), table_name="wallet_events")
    op.drop_index(op.f("ix_wallet_events_tx_signature"), table_name="wallet_events")
    op.drop_index(op.f("ix_wallet_events_token_mint"), table_name="wallet_events")
    op.drop_index(op.f("ix_wallet_events_event_time"), table_name="wallet_events")
    op.drop_table("wallet_events")

    op.drop_index(op.f("ix_wallet_cluster_members_wallet_address"), table_name="wallet_cluster_members")
    op.drop_table("wallet_cluster_members")

    op.drop_index(op.f("ix_candidate_tokens_token_mint"), table_name="candidate_tokens")
    op.drop_table("candidate_tokens")

    op.drop_table("wallet_clusters")

    op.drop_index(op.f("ix_wallet_beta_posteriors_wallet_address"), table_name="wallet_beta_posteriors")
    op.drop_table("wallet_beta_posteriors")

    op.drop_index(op.f("ix_tracked_wallets_wallet_address"), table_name="tracked_wallets")
    op.drop_table("tracked_wallets")

    bind = op.get_bind()
    for enum_type in (
        outcome_label_enum,
        delivery_status_enum,
        alert_channel_enum,
        risk_level_enum,
        decision_enum,
        launch_source_enum,
        candidate_status_enum,
        event_type_enum,
        cluster_type_enum,
        wallet_lifecycle_enum,
        wallet_type_enum,
    ):
        enum_type.drop(bind, checkfirst=True)
