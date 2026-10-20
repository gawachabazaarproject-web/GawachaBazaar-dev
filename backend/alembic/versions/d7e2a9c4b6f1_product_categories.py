"""product_categories: list a product under more than one category

Revision ID: d7e2a9c4b6f1
Revises: c3d5e7f9a1b2
Create Date: 2026-10-20 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7e2a9c4b6f1"
down_revision: str | None = "c3d5e7f9a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_categories",
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("product_id", "category_id"),
    )
    op.create_index("ix_product_categories_category_id", "product_categories", ["category_id"])


def downgrade() -> None:
    op.drop_index("ix_product_categories_category_id", table_name="product_categories")
    op.drop_table("product_categories")
