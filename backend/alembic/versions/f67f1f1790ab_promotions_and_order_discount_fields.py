"""promotions_and_order_discount_fields

Revision ID: f67f1f1790ab
Revises: 50946ed1400f
Create Date: 2026-09-15

Admin Panel Promotions module - the first phase to give this backend an
actual discount/promotion domain (confirmed absent in every prior admin-
panel Phase 1 audit: zero models, schemas, services, or endpoints
anywhere referenced "promotion", "coupon", or "discount" before this).

CATALOG DOMAIN (new tables):
- `promotions` - one row per promotion. `status` is the admin-set control
  (DRAFT/ACTIVE/PAUSED/DISABLED); the customer-facing SCHEDULED/EXPIRED
  states are computed from `starts_at`/`ends_at` at read time, never
  stored, so there is nothing to keep in sync with the clock. `code` is
  nullable+unique (an automatic promotion has no code); `discount_type`
  is PERCENTAGE or FIXED_AMOUNT only - FREE_DELIVERY was considered and
  rejected because this backend never charges a delivery fee to waive
  (see mobile app's BillBreakdownCard: "Delivery Partner Fee: FREE" is
  unconditional), and BUY_X_GET_Y was rejected per the spec's own "only
  implement if the backend architecture supports it correctly" - it
  would need new order-item-level free-unit mechanics this phase doesn't
  build. `stacking_policy` is fixed to `SINGLE_BEST` for every row for
  now (documented, deterministic: at most one promotion per order, the
  best-eligible one wins ties by priority then id) - no compatibility
  matrix exists yet to store, so there is no column for one.
- `promotion_targets` - PRODUCT/CATEGORY scoping, polymorphic like
  `stock_movements.reference_type/id` already is elsewhere in this schema.
- `promotion_eligible_customers` - explicit customer allow-list for the
  SPECIFIC customer-scope option.
- `promotion_redemptions` - one row per order a promotion was actually
  applied to (UNIQUE(order_id) - an order can carry at most one
  promotion under the SINGLE_BEST policy above). `status` lets a
  cancelled order's redemption be marked REVERSED (freeing global/
  per-customer usage limits) without ever deleting the historical row.

ORDERS TABLE (additive columns, backward-compatible):
- `subtotal_amount` - the pre-discount sum of order items; this is what
  `total_amount` meant before this migration. Backfilled from the
  existing `total_amount` for every historical row (discount_amount=0),
  so no historical order's meaning changes.
- `discount_amount` (default 0) and `promotion_id`/`applied_promo_code`
  (both nullable) - the promotion applied at checkout, snapshotted
  immutably. `total_amount` itself is UNCHANGED in column definition -
  its *meaning* becomes "what the customer actually pays" (subtotal
  minus discount), which is what `PaymentService`/`FulfillmentService`
  already read it as (see app/services/payment.py:137,
  app/services/fulfillment.py:184) - so this migration does not need to
  touch either of those call sites, only how OrderService.checkout
  computes the value going into that same column from now on.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f67f1f1790ab"
down_revision = "50946ed1400f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "promotions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("customer_title", sa.String(length=150), nullable=True),
        sa.Column("customer_description", sa.Text(), nullable=True),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("discount_type", sa.String(length=20), nullable=False),
        sa.Column("discount_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_discount_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("min_order_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("min_quantity", sa.Numeric(12, 3), nullable=True),
        sa.Column("customer_scope", sa.String(length=20), nullable=False, server_default="ALL"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
        sa.Column("stacking_policy", sa.String(length=20), nullable=False, server_default="SINGLE_BEST"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("usage_limit_total", sa.Integer(), nullable=True),
        sa.Column("usage_limit_per_customer", sa.Integer(), nullable=True),
        sa.Column("redemption_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name="fk_promotions_created_by_user_id_users", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "discount_type IN ('PERCENTAGE', 'FIXED_AMOUNT')", name="ck_promotions_discount_type"
        ),
        sa.CheckConstraint("discount_value > 0", name="ck_promotions_discount_value"),
        sa.CheckConstraint(
            "discount_type != 'PERCENTAGE' OR discount_value <= 100", name="ck_promotions_percentage_max"
        ),
        sa.CheckConstraint(
            "customer_scope IN ('ALL', 'NEW_CUSTOMERS', 'EXISTING_CUSTOMERS', 'SPECIFIC')",
            name="ck_promotions_customer_scope",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'PAUSED', 'DISABLED')", name="ck_promotions_status"
        ),
        sa.CheckConstraint("stacking_policy IN ('SINGLE_BEST')", name="ck_promotions_stacking_policy"),
        sa.CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="ck_promotions_ends_at"),
        sa.CheckConstraint(
            "usage_limit_total IS NULL OR usage_limit_total > 0", name="ck_promotions_usage_limit_total"
        ),
        sa.CheckConstraint(
            "usage_limit_per_customer IS NULL OR usage_limit_per_customer > 0",
            name="ck_promotions_usage_limit_per_customer",
        ),
    )
    op.create_index("uq_promotions_code", "promotions", ["code"], unique=True, postgresql_where=sa.text("code IS NOT NULL"))
    op.create_index("ix_promotions_status", "promotions", ["status"])
    op.create_index("ix_promotions_starts_at", "promotions", ["starts_at"])
    op.create_index("ix_promotions_ends_at", "promotions", ["ends_at"])

    op.create_table(
        "promotion_targets",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("promotion_id", sa.BigInteger(), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["promotion_id"], ["promotions.id"], name="fk_promotion_targets_promotion_id", ondelete="CASCADE"
        ),
        sa.CheckConstraint("target_type IN ('PRODUCT', 'CATEGORY')", name="ck_promotion_targets_target_type"),
        sa.UniqueConstraint("promotion_id", "target_type", "target_id", name="uq_promotion_targets_unique"),
    )
    op.create_index("ix_promotion_targets_promotion_id", "promotion_targets", ["promotion_id"])
    op.create_index("ix_promotion_targets_target", "promotion_targets", ["target_type", "target_id"])

    op.create_table(
        "promotion_eligible_customers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("promotion_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["promotion_id"], ["promotions.id"], name="fk_promotion_eligible_customers_promotion_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_promotion_eligible_customers_user_id", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("promotion_id", "user_id", name="uq_promotion_eligible_customers_unique"),
    )
    op.create_index("ix_promotion_eligible_customers_promotion_id", "promotion_eligible_customers", ["promotion_id"])

    op.create_table(
        "promotion_redemptions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("promotion_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_user_id", sa.BigInteger(), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="APPLIED"),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["promotion_id"], ["promotions.id"], name="fk_promotion_redemptions_promotion_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name="fk_promotion_redemptions_order_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["customer_user_id"], ["users.id"], name="fk_promotion_redemptions_customer_user_id", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("discount_amount >= 0", name="ck_promotion_redemptions_discount_amount"),
        sa.CheckConstraint("status IN ('APPLIED', 'REVERSED')", name="ck_promotion_redemptions_status"),
        sa.UniqueConstraint("order_id", name="uq_promotion_redemptions_order_id"),
    )
    op.create_index("ix_promotion_redemptions_promotion_id", "promotion_redemptions", ["promotion_id"])
    op.create_index("ix_promotion_redemptions_customer_user_id", "promotion_redemptions", ["customer_user_id"])

    # Orders: additive pricing columns.
    op.add_column("orders", sa.Column("subtotal_amount", sa.Numeric(12, 2), nullable=True))
    op.execute("UPDATE orders SET subtotal_amount = total_amount WHERE subtotal_amount IS NULL")
    op.alter_column("orders", "subtotal_amount", nullable=False)
    op.add_column(
        "orders", sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0")
    )
    op.add_column("orders", sa.Column("promotion_id", sa.BigInteger(), nullable=True))
    op.add_column("orders", sa.Column("applied_promo_code", sa.String(length=50), nullable=True))
    op.create_foreign_key(
        "fk_orders_promotion_id_promotions", "orders", "promotions", ["promotion_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_check_constraint("ck_orders_subtotal_amount", "orders", "subtotal_amount >= 0")
    op.create_check_constraint("ck_orders_discount_amount", "orders", "discount_amount >= 0")
    op.create_check_constraint(
        "ck_orders_discount_not_exceeding_subtotal", "orders", "discount_amount <= subtotal_amount"
    )


def downgrade() -> None:
    op.drop_constraint("ck_orders_discount_not_exceeding_subtotal", "orders", type_="check")
    op.drop_constraint("ck_orders_discount_amount", "orders", type_="check")
    op.drop_constraint("ck_orders_subtotal_amount", "orders", type_="check")
    op.drop_constraint("fk_orders_promotion_id_promotions", "orders", type_="foreignkey")
    op.drop_column("orders", "applied_promo_code")
    op.drop_column("orders", "promotion_id")
    op.drop_column("orders", "discount_amount")
    op.drop_column("orders", "subtotal_amount")

    op.drop_index("ix_promotion_redemptions_customer_user_id", table_name="promotion_redemptions")
    op.drop_index("ix_promotion_redemptions_promotion_id", table_name="promotion_redemptions")
    op.drop_table("promotion_redemptions")

    op.drop_index("ix_promotion_eligible_customers_promotion_id", table_name="promotion_eligible_customers")
    op.drop_table("promotion_eligible_customers")

    op.drop_index("ix_promotion_targets_target", table_name="promotion_targets")
    op.drop_index("ix_promotion_targets_promotion_id", table_name="promotion_targets")
    op.drop_table("promotion_targets")

    op.drop_index("ix_promotions_ends_at", table_name="promotions")
    op.drop_index("ix_promotions_starts_at", table_name="promotions")
    op.drop_index("ix_promotions_status", table_name="promotions")
    op.drop_index("uq_promotions_code", table_name="promotions")
    op.drop_table("promotions")
