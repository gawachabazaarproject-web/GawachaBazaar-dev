"""drop verification-code tables (login OTP, password reset, contact change)

The Resend email integration and every flow that depended on delivering a
code were removed: customers log in with password only, password resets and
email/phone changes are done directly by an ADMIN in the Admin panel
(CustomerService.admin_reset_password / admin_update_contact). These three
tables only ever held short-lived challenge rows, so nothing of lasting
value is dropped.

downgrade() recreates the tables exactly as their original migrations
(a1024b757d60, c3f8a91e6b2d, b7e2a9f4c1d3) did - empty, since the rows were
ephemeral codes.

Revision ID: efae4c4402ba
Revises: d4e7b2c9a1f6
Create Date: 2026-09-27 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'efae4c4402ba'
down_revision: str | None = 'd4e7b2c9a1f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_contact_change_requests_pending", table_name="contact_change_requests")
    op.drop_index("ix_contact_change_requests_user_id", table_name="contact_change_requests")
    op.drop_table("contact_change_requests")
    op.drop_index("ix_password_reset_challenges_user_id", table_name="password_reset_challenges")
    op.drop_table("password_reset_challenges")
    op.drop_index("ix_login_otp_challenges_user_id", table_name="login_otp_challenges")
    op.drop_table("login_otp_challenges")


def downgrade() -> None:
    op.create_table('login_otp_challenges',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('challenge_token', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('code_hash', sa.Text(), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('device_name', sa.String(length=100), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('PENDING', 'VERIFIED', 'EXPIRED')", name='ck_login_otp_challenges_status'),
    sa.CheckConstraint('attempts >= 0', name='ck_login_otp_challenges_attempts'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('challenge_token')
    )
    op.create_index('ix_login_otp_challenges_user_id', 'login_otp_challenges', ['user_id'], unique=False)

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

    op.create_table(
        "contact_change_requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field", sa.String(20), nullable=False),
        sa.Column("new_value", sa.String(255), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column(
            "requested_by_admin_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("field IN ('EMAIL', 'PHONE')", name="ck_contact_change_requests_field"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'VERIFIED', 'EXPIRED', 'CANCELLED')",
            name="ck_contact_change_requests_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_contact_change_requests_attempts"),
    )
    op.create_index("ix_contact_change_requests_user_id", "contact_change_requests", ["user_id"])
    op.create_index(
        "uq_contact_change_requests_pending",
        "contact_change_requests",
        ["user_id", "field"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )
