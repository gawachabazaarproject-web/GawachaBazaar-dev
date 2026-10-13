"""merge push_tokens and promotion_offers heads

Revision ID: f1a2b3c4d5e6
Revises: a1c9e3d7b520, e4a7c1b9d036
Create Date: 2026-10-13 16:00:00.000000

"""
from collections.abc import Sequence

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = ("a1c9e3d7b520", "e4a7c1b9d036")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
