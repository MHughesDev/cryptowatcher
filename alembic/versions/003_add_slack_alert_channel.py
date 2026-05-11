"""add slack alert channel

Revision ID: 003_add_slack_alert_channel
Revises: 002_wallet_outcome_applications
Create Date: 2026-05-10 00:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "003_add_slack_alert_channel"
down_revision = "002_wallet_outcome_applications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE alert_channel ADD VALUE IF NOT EXISTS 'SLACK'")


def downgrade() -> None:
    # PostgreSQL enum value removal is non-trivial and intentionally skipped.
    pass
