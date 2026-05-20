"""allow outreach logs without a campaign

Revision ID: 20260510_0002
Revises: 20260506_0001
Create Date: 2026-05-10 00:02:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260510_0002"
down_revision = "20260506_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("outreach_logs", "campaign_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("outreach_logs", "campaign_id", existing_type=sa.UUID(), nullable=False)
