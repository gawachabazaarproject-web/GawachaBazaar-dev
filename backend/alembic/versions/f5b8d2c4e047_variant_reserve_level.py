"""variant reserve level (stock to keep in reserve)

Revision ID: f5b8d2c4e047
Revises: e4a7c1b9d036
Create Date: 2026-10-10 05:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f5b8d2c4e047"
down_revision: str | None = "e4a7c1b9d036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NULL = use the default reserve (see app/services/stock_levels.py).
    op.add_column("product_variants", sa.Column("reserve_level", sa.Numeric(12, 3), nullable=True))
    op.create_check_constraint(
        "ck_product_variants_reserve_level", "product_variants", "reserve_level IS NULL OR reserve_level >= 0"
    )


def downgrade() -> None:
    op.drop_constraint("ck_product_variants_reserve_level", "product_variants", type_="check")
    op.drop_column("product_variants", "reserve_level")
