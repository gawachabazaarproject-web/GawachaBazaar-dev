"""admin_action_audit_log

Revision ID: 50946ed1400f
Revises: 6c1e3ba0420b
Create Date: 2026-09-15

Admin Panel Phase 5 (Order Action Auditability):

Creates `admin_action_logs` - a generic, append-only audit ledger for
admin-panel mutations, following the same immutable-ledger pattern already
established by `stock_movements` (Phase 4). `resource_type`/`resource_id`
is a deliberately generic polymorphic reference so every future admin
module (products, inventory, promotions, ...) writes into this one table
instead of each growing its own bespoke audit columns - `orders.
cancelled_by_user_id` and `refunds.approved_by_user_id` remain untouched
and still authoritative for their own tables; this is the cross-module
"what did admins do, when" view the eventual Audit Log admin module reads
from. No update/delete path exists or should ever exist for this table.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "50946ed1400f"
down_revision = "6c1e3ba0420b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_action_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("admin_user_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.BigInteger(), nullable=False),
        sa.Column("previous_state", sa.String(length=50), nullable=True),
        sa.Column("new_state", sa.String(length=50), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["admin_user_id"],
            ["users.id"],
            name="fk_admin_action_logs_admin_user_id_users",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_admin_action_logs_admin_user_id",
        "admin_action_logs",
        ["admin_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_admin_action_logs_resource",
        "admin_action_logs",
        ["resource_type", "resource_id"],
        unique=False,
    )
    op.create_index(
        "ix_admin_action_logs_created_at",
        "admin_action_logs",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_admin_action_logs_created_at", table_name="admin_action_logs")
    op.drop_index("ix_admin_action_logs_resource", table_name="admin_action_logs")
    op.drop_index("ix_admin_action_logs_admin_user_id", table_name="admin_action_logs")
    op.drop_table("admin_action_logs")
