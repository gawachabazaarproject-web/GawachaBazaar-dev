"""notification events (push idempotency)

Revision ID: c3d5e7f9a1b2
Revises: f1a2b3c4d5e6
Create Date: 2026-10-18 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d5e7f9a1b2"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("dedupe_key", sa.String(128), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("dedupe_key", name="uq_notification_events_dedupe_key"),
    )
    op.create_index("ix_notification_events_user_id", "notification_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notification_events_user_id", table_name="notification_events")
    op.drop_table("notification_events")
