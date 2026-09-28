"""ads

Revision ID: d4e7b2c9a1f6
Revises: c3f8a91e6b2d
Create Date: 2026-09-21 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4e7b2c9a1f6'
down_revision: str | None = 'c3f8a91e6b2d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('ads',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('brand_name', sa.String(length=150), nullable=False),
    sa.Column('image_url', sa.Text(), nullable=False),
    sa.Column('link_url', sa.Text(), nullable=True),
    sa.Column('display_order', sa.Integer(), server_default='0', nullable=False),
    sa.Column('status', sa.String(length=20), server_default='ACTIVE', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_ads_status'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ads_status_display_order', 'ads', ['status', 'display_order'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ads_status_display_order', table_name='ads')
    op.drop_table('ads')
