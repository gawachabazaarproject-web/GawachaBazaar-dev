"""seed_baseline_roles

Revision ID: 37bbdf459894
Revises: d051168c1d3d
Create Date: 2026-09-11 16:41:39.740347

Reference-data migration: seeds the six baseline platform roles.

This is intentionally NOT a schema change - `roles` already has the correct
shape from Phase 1. Without this data, public registration cannot assign the
CUSTOMER role and fails on any freshly-migrated database.

Seeding roles does not authorize anyone. No `users` or `user_roles` rows are
created or modified here - role membership remains a deliberate, explicit
application-level operation.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "37bbdf459894"
down_revision: str | None = "d051168c1d3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Six active baseline roles. Farmer is intentionally absent - Farmer/Farm
# remain future capabilities and are not an active actor (see
# docs/architecture/ARCHITECTURE.md).
_BASELINE_ROLES: tuple[tuple[str, str], ...] = (
    ("CUSTOMER", "Retail customer browsing catalog and placing orders."),
    ("WHOLESALER", "Supply partner providing produce batches into the supply chain."),
    ("ADMIN", "Platform superuser overseeing catalog, pricing, and configuration."),
    ("HUB_STAFF", "Hub facility staff handling sorting, grading, and quality checks."),
    ("OPERATIONS", "Operations staff handling inventory and packaging workflows."),
    ("DELIVERY_PARTNER", "Logistics personnel handling last-mile delivery dispatch."),
)


def upgrade() -> None:
    bind = op.get_bind()
    roles_table = sa.table(
        "roles",
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )

    # Idempotent by role name: safe to run against a database where some or
    # all baseline roles already exist (e.g. inserted manually in an earlier
    # environment) without raising a duplicate-key error.
    insert_stmt = pg_insert(roles_table).values(
        [{"name": name, "description": description} for name, description in _BASELINE_ROLES]
    )
    insert_stmt = insert_stmt.on_conflict_do_nothing(index_elements=["name"])
    bind.execute(insert_stmt)


def downgrade() -> None:
    bind = op.get_bind()
    role_names = [name for name, _ in _BASELINE_ROLES]

    in_use = bind.execute(
        sa.text(
            "SELECT r.name FROM roles r "
            "JOIN user_roles ur ON ur.role_id = r.id "
            "WHERE r.name = ANY(:names)"
        ),
        {"names": role_names},
    ).fetchall()
    if in_use:
        in_use_names = ", ".join(row[0] for row in in_use)
        raise RuntimeError(
            f"Downgrade safety check failed: role(s) still assigned to users via "
            f"user_roles: {in_use_names}. Cannot remove baseline roles that are in use."
        )

    bind.execute(
        sa.text("DELETE FROM roles WHERE name = ANY(:names)"),
        {"names": role_names},
    )
