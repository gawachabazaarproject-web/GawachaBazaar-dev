"""promotion offers: banner image + carousel flag, 4 starter offers

Also MERGES the two migration heads (c1e5f7a9b023 checkout_sessions and
d6b1f3a5c024 ad_card_text) that were created in parallel, so `alembic upgrade
head` has a single head again without editing either of them.

Revision ID: e4a7c1b9d036
Revises: c1e5f7a9b023, d6b1f3a5c024
Create Date: 2026-10-10 03:40:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4a7c1b9d036"
down_revision: str | Sequence[str] | None = ("c1e5f7a9b023", "d6b1f3a5c024")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IMG = "https://images.unsplash.com/{id}?w=1200&h=800&fit=crop&q=80"

# (code, name, title, description, type, value, max_discount, min_order, scope, priority, image id)
_OFFERS = [
    (
        "WELCOME50", "Welcome offer", "Rs 50 off your first Bazaar",
        "New to Gawacha Bazaar? Fresh from the farm, with Rs 50 off your first order.",
        "FIXED_AMOUNT", 50, None, 299, "NEW_CUSTOMERS", 10, "photo-1488459716781-31db52582fe9",
    ),
    (
        "BAZAAR100", "Bazaar saver", "Fill your Bazaar, save Rs 100",
        "Rs 100 off bigger baskets - and pick 15 different products for free delivery too.",
        "FIXED_AMOUNT", 100, None, 999, "ALL", 20, "photo-1566385101042-1a0aa0c1268c",
    ),
    (
        "FRESH10", "Farm-fresh 10", "10% off farm-fresh picks",
        "Fruits and vegetables picked at dawn, now 10% cheaper on your basket.",
        "PERCENTAGE", 10, 100, 399, "ALL", 30, "photo-1610832958506-aa56368176cf",
    ),
    (
        "WEEKEND15", "Weekend mandi", "Weekend mandi special: 15% off",
        "Stock up for the week - 15% off your basket, up to Rs 150.",
        "PERCENTAGE", 15, 150, 599, "ALL", 40, "photo-1540420773420-3366772f4999",
    ),
]


def upgrade() -> None:
    op.add_column("promotions", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column(
        "promotions",
        sa.Column("show_in_carousel", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    # Starter offers. They need an owner (promotions.created_by_user_id is NOT
    # NULL), so seed only when an ADMIN user already exists, and never
    # duplicate a code that is already taken.
    insert = sa.text(
        """
        INSERT INTO promotions (
            name, customer_title, customer_description, code, discount_type, discount_value,
            max_discount_amount, min_order_value, customer_scope, status, stacking_policy,
            priority, starts_at, created_by_user_id, image_url, show_in_carousel
        )
        SELECT CAST(:name AS varchar), CAST(:title AS varchar), CAST(:description AS text),
               CAST(:code AS varchar), CAST(:dtype AS varchar), CAST(:value AS numeric),
               CAST(:max_discount AS numeric), CAST(:min_order AS numeric), CAST(:scope AS varchar),
               'ACTIVE', 'SINGLE_BEST', CAST(:priority AS integer), now(), admin.id,
               CAST(:image AS text), true
        FROM (
            SELECT u.id FROM users u
            JOIN user_roles ur ON ur.user_id = u.id
            JOIN roles r ON r.id = ur.role_id
            WHERE r.name = 'ADMIN'
            ORDER BY u.id LIMIT 1
        ) AS admin
        WHERE NOT EXISTS (SELECT 1 FROM promotions p WHERE p.code = CAST(:code AS varchar))
        """
    )
    bind = op.get_bind()
    for code, name, title, description, dtype, value, max_discount, min_order, scope, priority, image in _OFFERS:
        bind.execute(
            insert,
            {
                "name": name, "title": title, "description": description, "code": code, "dtype": dtype,
                "value": value, "max_discount": max_discount, "min_order": min_order, "scope": scope,
                "priority": priority, "image": _IMG.format(id=image),
            },
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM promotions WHERE code IN ('WELCOME50', 'BAZAAR100', 'FRESH10', 'WEEKEND15') "
            "AND redemption_count = 0"
        )
    )
    op.drop_column("promotions", "show_in_carousel")
    op.drop_column("promotions", "image_url")
