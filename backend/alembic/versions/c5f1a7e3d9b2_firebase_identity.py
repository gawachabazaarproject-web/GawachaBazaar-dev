"""firebase identity: users.firebase_uid, optional email/phone/password, drop auth_sessions

Firebase Authentication becomes the identity provider. The backend stops
issuing its own access/refresh tokens, so `auth_sessions` (refresh-token
hashes) is dropped - every outstanding backend session ends and clients
sign in again through Firebase.

- users.firebase_uid: UNIQUE link to the Firebase user. NULL only for
  pre-Firebase accounts until their first sign-in migrates them.
- users.email / users.phone: nullable (phone-OTP users have no email,
  Google users have no phone) but still UNIQUE; at least one must be set.
- users.password_hash: nullable; only legacy, not-yet-migrated rows keep it.

downgrade() cannot restore a password for accounts created in Firebase, so
it refuses if any row has lost its email, phone, or password hash.

Revision ID: c5f1a7e3d9b2
Revises: efae4c4402ba
Create Date: 2026-09-30 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5f1a7e3d9b2"
down_revision: str | None = "efae4c4402ba"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("firebase_uid", sa.String(length=128), nullable=True))
    op.create_unique_constraint("users_firebase_uid_key", "users", ["firebase_uid"])
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=True)
    op.alter_column("users", "phone", existing_type=sa.String(length=20), nullable=True)
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=True)
    op.create_check_constraint(
        "ck_users_email_or_phone", "users", "email IS NOT NULL OR phone IS NOT NULL"
    )

    op.drop_index("ix_auth_sessions_revoked_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")


def downgrade() -> None:
    conn = op.get_bind()
    blocked = conn.execute(
        sa.text(
            "SELECT count(*) FROM users "
            "WHERE email IS NULL OR phone IS NULL OR password_hash IS NULL"
        )
    ).scalar()
    if blocked:
        raise RuntimeError(
            f"{blocked} user(s) have no email, phone, or password hash (Firebase-only "
            "accounts); the pre-Firebase schema cannot represent them."
        )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("refresh_token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_name", sa.String(length=150), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_index("ix_auth_sessions_revoked_at", "auth_sessions", ["revoked_at"])

    op.drop_constraint("ck_users_email_or_phone", "users", type_="check")
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=False)
    op.alter_column("users", "phone", existing_type=sa.String(length=20), nullable=False)
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=False)
    op.drop_constraint("users_firebase_uid_key", "users", type_="unique")
    op.drop_column("users", "firebase_uid")
