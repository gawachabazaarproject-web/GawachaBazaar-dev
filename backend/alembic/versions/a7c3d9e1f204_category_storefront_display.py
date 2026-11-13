"""categories: storefront display settings (tile colour, badge, visibility)

Revision ID: a7c3d9e1f204
Revises: e5f6a7b80923
Create Date: 2026-11-13 10:00:00.000000

Additive only. Existing categories keep their current behaviour: they stay
visible on the homepage and in the catalog (both flags default TRUE).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7c3d9e1f204"
down_revision: str | None = "e5f6a7b80923"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("categories", sa.Column("background_color", sa.String(length=7), nullable=True))
    op.add_column("categories", sa.Column("badge_text", sa.String(length=24), nullable=True))
    op.add_column(
        "categories",
        sa.Column("show_on_homepage", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "categories",
        sa.Column("show_in_catalog", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "categories",
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "ck_categories_background_color_hex",
        "categories",
        "background_color IS NULL OR background_color ~ '^#[0-9A-Fa-f]{6}$'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_categories_background_color_hex", "categories", type_="check")
    op.drop_column("categories", "is_featured")
    op.drop_column("categories", "show_in_catalog")
    op.drop_column("categories", "show_on_homepage")
    op.drop_column("categories", "badge_text")
    op.drop_column("categories", "background_color")
