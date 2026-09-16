"""drop_batch_supplier_or_wholesaler_check

Revision ID: 1fe5143343fd
Revises: 6f335f6934e6
Create Date: 2026-09-16 10:01:46.907746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1fe5143343fd'
down_revision: Union[str, None] = '6f335f6934e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Autogenerate does not detect CHECK constraint changes - written by
    # hand. An admin adding stock directly (e.g. the Admin panel's
    # Receive Stock flow) has no supplier/wholesaler to attribute a batch
    # to; this constraint made that impossible. Both columns stay
    # optional FKs - a supplier/wholesaler can still be set whenever that
    # traceability is actually wanted.
    op.drop_constraint("ck_batches_supplier_or_wholesaler", "batches", type_="check")


def downgrade() -> None:
    op.create_check_constraint(
        "ck_batches_supplier_or_wholesaler",
        "batches",
        "wholesaler_user_id IS NOT NULL OR supplier_id IS NOT NULL",
    )
