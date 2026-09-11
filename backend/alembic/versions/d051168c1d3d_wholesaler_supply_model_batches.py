"""wholesaler_supply_model_batches

Revision ID: d051168c1d3d
Revises: 4d9160d1bcc6
Create Date: 2026-09-11 06:09:08.362423

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d051168c1d3d"
down_revision: str | None = "4d9160d1bcc6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    batch_count = bind.execute(sa.text("SELECT COUNT(*) FROM batches")).scalar()
    if batch_count and batch_count > 0:
        raise RuntimeError(
            f"Migration safety check failed: 'batches' table contains {batch_count} existing rows. "
            "Cannot safely add non-nullable 'wholesaler_user_id' column without valid wholesaler mapping."
        )

    op.add_column(
        "batches",
        sa.Column("wholesaler_user_id", sa.BigInteger(), nullable=False),
    )
    op.alter_column(
        "batches",
        "farm_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.create_index(
        "ix_batches_wholesaler_user_id",
        "batches",
        ["wholesaler_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_batches_wholesaler_user_id_users",
        "batches",
        "users",
        ["wholesaler_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    bind = op.get_bind()
    null_farm_batches = bind.execute(
        sa.text("SELECT COUNT(*) FROM batches WHERE farm_id IS NULL")
    ).scalar()
    if null_farm_batches and null_farm_batches > 0:
        raise RuntimeError(
            f"Downgrade safety check failed: 'batches' table contains {null_farm_batches} rows with NULL farm_id. "
            "Cannot revert 'farm_id' to NOT NULL without data repair."
        )

    op.drop_constraint(
        "fk_batches_wholesaler_user_id_users",
        "batches",
        type_="foreignkey",
    )
    op.drop_index("ix_batches_wholesaler_user_id", table_name="batches")
    op.alter_column(
        "batches",
        "farm_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.drop_column("batches", "wholesaler_user_id")
