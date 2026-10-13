"""home_slides

Revision ID: a8c3d5e7f901
Revises: d7a2b9c41e60
Create Date: 2026-10-10 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8c3d5e7f901"
down_revision: str | None = "d7a2b9c41e60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The four slides the app previously hardcoded (mobile/src/utils/campaignSlides.ts).
_SEED = [
    (
        "SEASONAL MARKET", "Gaon se Nagpur", "tak.",
        "Fresh, unadulterated harvest picked at dawn from Katol, Wardha & Saoner orchards.",
        "https://images.unsplash.com/photo-1489450278009-822e9be04dff?w=1200&h=1500&fit=crop&q=80",
        "Explore today's market",
    ),
    (
        "OUR PROMISE", "Gawacha", "Swad Vachan.",
        "Every rupee you spend directly empowers Vidarbha smallholders, with no middlemen commissions.",
        "https://images.unsplash.com/photo-1500937386664-56d1dfef3854?w=1200&h=1500&fit=crop&q=80",
        "Read our story",
    ),
    (
        "VILLAGE SPECIALS", "Vidarbha,", "on your plate.",
        "Toor dal, cold-pressed oils and dryland staples sourced directly from Vidarbha's smallholder belt.",
        "https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=1200&h=1500&fit=crop&q=80",
        "Shop the specialties",
    ),
    (
        "FRESHNESS", "Picked", "at dawn.",
        "Nothing sits in cold storage - today's harvest reaches Nagpur kitchens the same evening.",
        "https://images.unsplash.com/photo-1610348725531-843dff563e2c?w=1200&h=1500&fit=crop&q=80",
        "See today's harvest",
    ),
]


def upgrade() -> None:
    table = op.create_table(
        "home_slides",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("script_suffix", sa.String(length=150), nullable=True),
        sa.Column("body", sa.Text(), server_default="", nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("cta_label", sa.String(length=80), server_default="", nullable=False),
        sa.Column("link_url", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_home_slides_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_home_slides_status_display_order", "home_slides", ["status", "display_order"], unique=False
    )
    op.bulk_insert(
        table,
        [
            {
                "label": label,
                "title": title,
                "script_suffix": suffix,
                "body": body,
                "image_url": image,
                "cta_label": cta,
                "display_order": i,
                "status": "ACTIVE",
            }
            for i, (label, title, suffix, body, image, cta) in enumerate(_SEED)
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_home_slides_status_display_order", table_name="home_slides")
    op.drop_table("home_slides")
