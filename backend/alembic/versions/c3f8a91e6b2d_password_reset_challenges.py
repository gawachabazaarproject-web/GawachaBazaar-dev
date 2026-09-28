"""password_reset_challenges

Revision ID: c3f8a91e6b2d
Revises: 1fe5143343fd
Create Date: 2026-09-18 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3f8a91e6b2d'
down_revision: str | None = '1fe5143343fd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('password_reset_challenges',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('code_hash', sa.Text(), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('PENDING', 'VERIFIED', 'EXPIRED')", name='ck_password_reset_challenges_status'),
    sa.CheckConstraint('attempts >= 0', name='ck_password_reset_challenges_attempts'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_password_reset_challenges_user_id', 'password_reset_challenges', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_password_reset_challenges_user_id', table_name='password_reset_challenges')
    op.drop_table('password_reset_challenges')
