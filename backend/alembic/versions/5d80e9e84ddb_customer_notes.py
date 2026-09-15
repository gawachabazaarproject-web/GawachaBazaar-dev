"""customer_notes

Revision ID: 5d80e9e84ddb
Revises: f67f1f1790ab
Create Date: 2026-09-16

Admin Panel Customers module. Confirmed (Phase 1 audit for this module) that
no admin/support notes concept exists anywhere in the backend - "note" hits
elsewhere in the schema are unrelated (bulk-order internal notes, quote
version notes, supplier notes), none of them customer-support notes attached
to a User.

`customer_notes` - a plain support-note ledger, editable in place (unlike
`admin_action_logs`, which is append-only): a note is working context an
agent revises as understanding improves, not a historical fact - so this
table gets its own `updated_at`, and edits are what `PATCH
/customers/admin/notes/{id}` audits via `admin_action_logs` (before/after
text), not something this table itself needs to version.

`user_id` -> the customer the note is about (CASCADE: a note about a user
has no purpose once that user identity is gone - mirrors `addresses.user_id`,
the only other per-customer child table with this exact ondelete choice).
`author_admin_user_id` -> RESTRICT, matching every other "who did this"
column in this codebase (`orders.cancelled_by_user_id`,
`refunds.approved_by_user_id`, `promotions.created_by_user_id`): an admin
account is never deleted out from under their own history.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "5d80e9e84ddb"
down_revision = "f67f1f1790ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_notes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_admin_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_customer_notes_user_id", "customer_notes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_customer_notes_user_id", table_name="customer_notes")
    op.drop_table("customer_notes")
