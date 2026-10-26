"""seed_catalog_staff_role

Revision ID: a8d2f4b6c0e1
Revises: d7e9a1c3b5f2
Create Date: 2026-10-26

Adds CATALOG_STAFF as an eighth baseline role, following the exact pattern of
`a3f8c1d2e6b4_seed_support_role.py` (pure reference-data insert, idempotent by
role name, no schema change).

CATALOG_STAFF adds and edits products, prices and photos and can view stock, but
cannot delete products, change stock, or touch staff/settings - see
app/core/permissions.py's ROLE_PERMISSIONS. Seeding the role does not authorize
anyone: user_roles membership remains an explicit assignment by an administrator.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8d2f4b6c0e1"
down_revision: str | None = "d7e9a1c3b5f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_ROLE = ("CATALOG_STAFF", "Catalogue staff who add and edit products, prices and photos.")


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
            "Downgrade safety check failed: CATALOG_STAFF is still assigned to users via user_roles."
        )
    bind.execute(sa.text("DELETE FROM roles WHERE name = :name"), {"name": _NEW_ROLE[0]})
