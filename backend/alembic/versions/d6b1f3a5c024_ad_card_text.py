"""ad card text

Revision ID: d6b1f3a5c024
Revises: c2a8e4f6b013
Create Date: 2026-10-10 01:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d6b1f3a5c024"
down_revision: str | None = "c2a8e4f6b013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ads", sa.Column("title", sa.String(80), nullable=True))
    op.add_column("ads", sa.Column("subtitle", sa.String(140), nullable=True))


def downgrade() -> None:
    op.drop_column("ads", "subtitle")
    op.drop_column("ads", "title")
