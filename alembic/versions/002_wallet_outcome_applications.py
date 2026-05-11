"""add wallet outcome applications idempotency ledger

Revision ID: 002_wallet_outcome_applications
Revises: 001_initial
Create Date: 2026-05-10 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "002_wallet_outcome_applications"
down_revision: str | None = "001_initial"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wallet_outcome_applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("token_outcome_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_mint", sa.String(length=64), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["token_outcome_id"], ["token_outcomes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wallet_address", "token_outcome_id"),
    )
    op.create_index(
        op.f("ix_wallet_outcome_applications_wallet_address"),
        "wallet_outcome_applications",
        ["wallet_address"],
        unique=False,
    )
    op.create_index(
        op.f("ix_wallet_outcome_applications_token_outcome_id"),
        "wallet_outcome_applications",
        ["token_outcome_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_wallet_outcome_applications_token_mint"),
        "wallet_outcome_applications",
        ["token_mint"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_wallet_outcome_applications_token_mint"), table_name="wallet_outcome_applications")
    op.drop_index(op.f("ix_wallet_outcome_applications_token_outcome_id"), table_name="wallet_outcome_applications")
    op.drop_index(op.f("ix_wallet_outcome_applications_wallet_address"), table_name="wallet_outcome_applications")
    op.drop_table("wallet_outcome_applications")
