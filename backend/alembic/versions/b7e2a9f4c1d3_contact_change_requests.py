"""contact_change_requests

Revision ID: b7e2a9f4c1d3
Revises: a3f8c1d2e6b4
Create Date: 2026-09-16

Admin Panel Customers module follow-up: a verification-backed workflow for
admin-initiated email/phone changes, closing the gap the Customers module's
final report disclosed ("editing a customer's name/email/phone from Admin
was intentionally not built: email/phone changes would need a verification
workflow that doesn't exist in this backend").

`contact_change_requests` - one row per requested change. The new value is
never written to `users.email`/`users.phone` until the holder of the new
contact method proves it by returning the code that was sent there (see
app/services/contact_change.py and app/services/notification_gateway.py).
Only `code_hash` is stored, never the raw code (same SHA-256-over-opaque-
secret precedent as `auth_sessions.refresh_token_hash`).

UNIQUE(user_id, field) WHERE status = 'PENDING' - at most one pending
request per user per field at a time, enforced at the database level so a
race between two admins requesting a change for the same field can't leave
two live codes with unrelated attempt counters.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b7e2a9f4c1d3"
down_revision = "a3f8c1d2e6b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_change_requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field", sa.String(20), nullable=False),
        sa.Column("new_value", sa.String(255), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column(
            "requested_by_admin_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("field IN ('EMAIL', 'PHONE')", name="ck_contact_change_requests_field"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'VERIFIED', 'EXPIRED', 'CANCELLED')",
            name="ck_contact_change_requests_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_contact_change_requests_attempts"),
    )
    op.create_index("ix_contact_change_requests_user_id", "contact_change_requests", ["user_id"])
    op.create_index(
        "uq_contact_change_requests_pending",
        "contact_change_requests",
        ["user_id", "field"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index("uq_contact_change_requests_pending", table_name="contact_change_requests")
    op.drop_index("ix_contact_change_requests_user_id", table_name="contact_change_requests")
    op.drop_table("contact_change_requests")
