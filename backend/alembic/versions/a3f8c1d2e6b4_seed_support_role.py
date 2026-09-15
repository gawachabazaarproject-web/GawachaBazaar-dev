"""seed_support_role

Revision ID: a3f8c1d2e6b4
Revises: 5d80e9e84ddb
Create Date: 2026-09-16

Admin Panel Customers module follow-up: adds SUPPORT as a seventh baseline
role, following the exact pattern of `37bbdf459894_seed_baseline_roles.py`
(pure reference-data insert, idempotent by role name, no schema change).

SUPPORT is a read-only, customer-facing-operations role - see
app/core/permissions.py's ROLE_PERMISSIONS, where it is granted
`customers.view` only (never `customers.view_sensitive`,
`customers.manage_status`, `customers.notes`, or `customers.manage_contact`).
It exists because every customers.* permission was previously ADMIN-only by
necessity: no non-ADMIN role existed for a support agent to hold. Seeding
the role does not, by itself, authorize anyone - user_roles membership
remains a deliberate, explicit assignment exactly as the original baseline
seed migration's docstring states.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f8c1d2e6b4"
down_revision: str | None = "5d80e9e84ddb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_ROLE = ("SUPPORT", "Customer-support agent with read-only access to customer records.")


def upgrade() -> None:
    bind = op.get_bind()
    roles_table = sa.table(
        "roles",
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    insert_stmt = pg_insert(roles_table).values([{"name": _NEW_ROLE[0], "description": _NEW_ROLE[1]}])
    insert_stmt = insert_stmt.on_conflict_do_nothing(index_elements=["name"])
    bind.execute(insert_stmt)


def downgrade() -> None:
    bind = op.get_bind()
    in_use = bind.execute(
        sa.text(
            "SELECT r.name FROM roles r "
            "JOIN user_roles ur ON ur.role_id = r.id "
            "WHERE r.name = :name"
        ),
        {"name": _NEW_ROLE[0]},
    ).fetchall()
    if in_use:
        raise RuntimeError(
            "Downgrade safety check failed: SUPPORT is still assigned to at least one user via "
            "user_roles. Cannot remove a baseline role that is in use."
        )
    bind.execute(sa.text("DELETE FROM roles WHERE name = :name"), {"name": _NEW_ROLE[0]})
