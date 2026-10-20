"""inventory_lots.is_share: stock assigned to a single size of a product

Revision ID: e8f3b1d5c7a2
Revises: d7e2a9c4b6f1
Create Date: 2026-10-20 15:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8f3b1d5c7a2"
down_revision: str | None = "d7e2a9c4b6f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UQ = "uq_inventory_lots_batch_variant_location"


def upgrade() -> None:
    op.add_column(
        "inventory_lots",
        sa.Column("is_share", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.drop_constraint(_UQ, "inventory_lots", type_="unique")
    op.create_unique_constraint(_UQ, "inventory_lots", ["batch_id", "variant_id", "location_id", "is_share"])


def downgrade() -> None:
    # Share lots cannot exist next to the ordinary lot of the same batch,
    # size and warehouse once the old constraint is back.
    op.execute(sa.text("DO $$ BEGIN IF EXISTS (SELECT 1 FROM inventory_lots WHERE is_share) THEN "
                       "RAISE EXCEPTION 'Release all stock shares before downgrading'; END IF; END $$;"))
    op.drop_constraint(_UQ, "inventory_lots", type_="unique")
    op.create_unique_constraint(_UQ, "inventory_lots", ["batch_id", "variant_id", "location_id"])
    op.drop_column("inventory_lots", "is_share")
