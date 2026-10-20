"""categories.sort_order: admin-controlled display order among siblings

Revision ID: f9a4c6e8b0d3
Revises: e8f3b1d5c7a2
Create Date: 2026-10-20 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f9a4c6e8b0d3"
down_revision: str | None = "e8f3b1d5c7a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    # Keep today's look (alphabetical) as the starting order per parent.
    op.execute(
        """
        UPDATE categories c SET sort_order = r.pos
        FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY parent_id ORDER BY name
            ) - 1 AS pos
            FROM categories
        ) r
        WHERE c.id = r.id
        """
    )


def downgrade() -> None:
    op.drop_column("categories", "sort_order")
