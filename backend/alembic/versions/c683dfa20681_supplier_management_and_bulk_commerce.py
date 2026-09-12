"""supplier_management_and_bulk_commerce

Revision ID: c683dfa20681
Revises: 2c63b696c267
Create Date: 2026-09-12

Phase 17 (Supplier Management + Bulk & Custom Commerce):

SUPPLIER DOMAIN
- Creates `suppliers` - an independent business entity, no `users` row or
  login required (Supplier is a business record, User is an
  authentication identity - deliberately kept separate per the spec).
- Creates `supplier_products` (supplier <-> product, many-to-many).
- Creates `supplier_evaluations` - append-only admin-entered performance
  history (quality/delivery/price/reliability/responsiveness/overall,
  0-5 scale), mirroring the existing append-only pattern used by
  `stock_movements`/`payment_transactions`. Never a single mutable
  "current score" column.

BATCH MIGRATION (additive, stage 1 of a documented multi-stage plan)
- Adds nullable `batches.supplier_id` (FK -> suppliers.id, RESTRICT).
- Relaxes `batches.wholesaler_user_id` from NOT NULL to NULLABLE. This is
  a safe relaxation: every existing row already has a value, so no data
  changes; no existing test/API path is affected since nothing in the
  active codebase requires the column to always be populated at the
  application layer beyond what the CHECK constraint below still
  enforces at the row level.
- Adds CHECK `ck_batches_supplier_or_wholesaler`: at least one of
  {wholesaler_user_id, supplier_id} must be non-null, so no batch ever
  loses a traceable origin. `wholesaler_user_id` is NOT dropped or
  renamed - full backward compatibility with Phase 8.1/2/11/12/13/15/16
  is preserved. Deprecating it fully is an explicit future stage, not
  attempted here.
- Adds nullable procurement facts Batch was missing to answer "what did
  we pay, when did we receive it, what's the receiving reference":
  `purchase_price`, `purchase_currency`, `received_date`,
  `receiving_reference`. Extending Batch directly (rather than a
  parallel `supplier_purchases` table) avoids duplicating facts that
  already belong to the same physical receiving event Batch represents.

BULK & CUSTOM COMMERCE DOMAIN
- Creates `bulk_customer_profiles` (one per User, optional B2B profile -
  no new role, no new auth flow).
- Creates `bulk_order_requests` + `bulk_order_request_items` - a request
  is NOT an Order (see architecture doc): items may reference an
  existing catalog `products.id` or, for a fully custom ask not yet in
  the catalog, a free-form `custom_item_name` instead (mutually
  exclusive via CHECK). `bulk_order_requests.order_id` (nullable,
  UNIQUE, FK -> orders.id) is the database-level backstop guaranteeing a
  request converts to at most one Order - never rely on the Python
  status check alone.
- Creates `quotes` (one per request) -> `quote_versions`
  (`DRAFT -> SENT -> {SUPERSEDED, ACCEPTED, REJECTED, EXPIRED,
  CANCELLED}` - admin never overwrites a sent quote; a renegotiation
  creates a new version, superseding but not destroying the previous
  one) -> `quote_items` (per-version line pricing, referencing a
  concrete `product_variants.id` since a quote commits to a specific
  sellable SKU, unlike the looser
  catalog-product-or-custom-text request item it prices).

Purely additive: no existing table is dropped, no existing column value
is rewritten, no existing constraint is tightened.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c683dfa20681"
down_revision: str | None = "2c63b696c267"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # suppliers
    # ------------------------------------------------------------------
    op.create_table(
        "suppliers",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("business_name", sa.String(length=200), nullable=False),
        sa.Column("contact_person", sa.String(length=150), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address_line_1", sa.String(length=255), nullable=True),
        sa.Column("address_line_2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name="ck_suppliers_status"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_suppliers"),
    )
    op.create_index("ix_suppliers_status", "suppliers", ["status"], unique=False)
    op.create_index(
        "ix_suppliers_business_name", "suppliers", ["business_name"], unique=False
    )

    # ------------------------------------------------------------------
    # supplier_products
    # ------------------------------------------------------------------
    op.create_table(
        "supplier_products",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("supplier_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("supplier_reference", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["suppliers.id"],
            name="fk_supplier_products_supplier_id", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_supplier_products_product_id", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_supplier_products"),
        sa.UniqueConstraint(
            "supplier_id", "product_id", name="uq_supplier_products_supplier_product"
        ),
    )
    op.create_index(
        "ix_supplier_products_supplier_id", "supplier_products", ["supplier_id"],
        unique=False,
    )
    op.create_index(
        "ix_supplier_products_product_id", "supplier_products", ["product_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # supplier_evaluations (append-only)
    # ------------------------------------------------------------------
    op.create_table(
        "supplier_evaluations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("supplier_id", sa.BigInteger(), nullable=False),
        sa.Column("evaluated_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("quality_rating", sa.Numeric(2, 1), nullable=False),
        sa.Column("delivery_rating", sa.Numeric(2, 1), nullable=False),
        sa.Column("price_rating", sa.Numeric(2, 1), nullable=False),
        sa.Column("reliability_rating", sa.Numeric(2, 1), nullable=False),
        sa.Column("responsiveness_rating", sa.Numeric(2, 1), nullable=False),
        sa.Column("overall_rating", sa.Numeric(2, 1), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quality_rating >= 0 AND quality_rating <= 5",
            name="ck_supplier_evaluations_quality_rating",
        ),
        sa.CheckConstraint(
            "delivery_rating >= 0 AND delivery_rating <= 5",
            name="ck_supplier_evaluations_delivery_rating",
        ),
        sa.CheckConstraint(
            "price_rating >= 0 AND price_rating <= 5",
            name="ck_supplier_evaluations_price_rating",
        ),
        sa.CheckConstraint(
            "reliability_rating >= 0 AND reliability_rating <= 5",
            name="ck_supplier_evaluations_reliability_rating",
        ),
        sa.CheckConstraint(
            "responsiveness_rating >= 0 AND responsiveness_rating <= 5",
            name="ck_supplier_evaluations_responsiveness_rating",
        ),
        sa.CheckConstraint(
            "overall_rating >= 0 AND overall_rating <= 5",
            name="ck_supplier_evaluations_overall_rating",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["suppliers.id"],
            name="fk_supplier_evaluations_supplier_id", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evaluated_by_user_id"], ["users.id"],
            name="fk_supplier_evaluations_evaluated_by_user_id", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_supplier_evaluations"),
    )
    op.create_index(
        "ix_supplier_evaluations_supplier_id", "supplier_evaluations", ["supplier_id"],
        unique=False,
    )
    op.create_index(
        "ix_supplier_evaluations_created_at", "supplier_evaluations", ["created_at"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # batches: additive supplier + procurement columns
    # ------------------------------------------------------------------
    op.add_column("batches", sa.Column("supplier_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "batches", sa.Column("purchase_price", sa.Numeric(12, 2), nullable=True)
    )
    op.add_column(
        "batches",
        sa.Column(
            "purchase_currency", sa.String(length=3), nullable=True
        ),
    )
    op.add_column("batches", sa.Column("received_date", sa.Date(), nullable=True))
    op.add_column(
        "batches", sa.Column("receiving_reference", sa.String(length=100), nullable=True)
    )
    op.create_foreign_key(
        "fk_batches_supplier_id", "batches", "suppliers", ["supplier_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_batches_supplier_id", "batches", ["supplier_id"], unique=False
    )
    op.alter_column("batches", "wholesaler_user_id", nullable=True)
    op.create_check_constraint(
        "ck_batches_supplier_or_wholesaler",
        "batches",
        "wholesaler_user_id IS NOT NULL OR supplier_id IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_batches_purchase_price",
        "batches",
        "purchase_price IS NULL OR purchase_price > 0",
    )

    # ------------------------------------------------------------------
    # bulk_customer_profiles
    # ------------------------------------------------------------------
    op.create_table(
        "bulk_customer_profiles",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("business_name", sa.String(length=200), nullable=False),
        sa.Column("business_type", sa.String(length=30), nullable=False),
        sa.Column("contact_person", sa.String(length=150), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "business_type IN ('RESTAURANT', 'HOTEL', 'CATERER', 'RETAILER', "
            "'OFFICE', 'INSTITUTION', 'EVENT', 'OTHER')",
            name="ck_bulk_customer_profiles_business_type",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_bulk_customer_profiles_user_id", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bulk_customer_profiles"),
        sa.UniqueConstraint("user_id", name="uq_bulk_customer_profiles_user_id"),
    )

    # ------------------------------------------------------------------
    # bulk_order_requests
    # ------------------------------------------------------------------
    op.create_table(
        "bulk_order_requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("customer_user_id", sa.BigInteger(), nullable=False),
        sa.Column("address_id", sa.BigInteger(), nullable=True),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("requested_delivery_date", sa.Date(), nullable=True),
        sa.Column("customer_notes", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED', 'UNDER_REVIEW', 'QUOTED', 'CUSTOMER_ACCEPTED', "
            "'CONVERTED_TO_ORDER', 'REJECTED', 'CANCELLED', 'EXPIRED')",
            name="ck_bulk_order_requests_status",
        ),
        sa.ForeignKeyConstraint(
            ["customer_user_id"], ["users.id"],
            name="fk_bulk_order_requests_customer_user_id", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["address_id"], ["addresses.id"],
            name="fk_bulk_order_requests_address_id", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"],
            name="fk_bulk_order_requests_order_id", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bulk_order_requests"),
        # Database-level idempotency backstop for conversion (never rely
        # on the Python status check alone): a request can become at most
        # one Order, enforced by Postgres, not just application logic.
        sa.UniqueConstraint("order_id", name="uq_bulk_order_requests_order_id"),
    )
    op.create_index(
        "ix_bulk_order_requests_customer_user_id", "bulk_order_requests",
        ["customer_user_id"], unique=False,
    )
    op.create_index(
        "ix_bulk_order_requests_status", "bulk_order_requests", ["status"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # bulk_order_request_items
    # ------------------------------------------------------------------
    op.create_table(
        "bulk_order_request_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("request_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=True),
        sa.Column("custom_item_name", sa.String(length=150), nullable=True),
        sa.Column("requested_quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("customer_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "unit IN ('KG', 'G', 'L', 'ML', 'UNIT', 'DOZEN', 'BOX', 'CRATE')",
            name="ck_bulk_order_request_items_unit",
        ),
        sa.CheckConstraint(
            "requested_quantity > 0", name="ck_bulk_order_request_items_quantity"
        ),
        sa.CheckConstraint(
            "(product_id IS NOT NULL) OR (custom_item_name IS NOT NULL)",
            name="ck_bulk_order_request_items_product_or_custom",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"], ["bulk_order_requests.id"],
            name="fk_bulk_order_request_items_request_id", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_bulk_order_request_items_product_id", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bulk_order_request_items"),
    )
    op.create_index(
        "ix_bulk_order_request_items_request_id", "bulk_order_request_items",
        ["request_id"], unique=False,
    )
    op.create_index(
        "ix_bulk_order_request_items_product_id", "bulk_order_request_items",
        ["product_id"], unique=False,
    )

    # ------------------------------------------------------------------
    # quotes
    # ------------------------------------------------------------------
    op.create_table(
        "quotes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("request_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["request_id"], ["bulk_order_requests.id"],
            name="fk_quotes_request_id", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_quotes"),
        sa.UniqueConstraint("request_id", name="uq_quotes_request_id"),
    )

    # ------------------------------------------------------------------
    # quote_versions (never overwritten - a new row per revision)
    # ------------------------------------------------------------------
    op.create_table(
        "quote_versions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("quote_id", sa.BigInteger(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'SENT', 'SUPERSEDED', 'ACCEPTED', 'REJECTED', "
            "'EXPIRED', 'CANCELLED')",
            name="ck_quote_versions_status",
        ),
        sa.CheckConstraint(
            "version_number > 0", name="ck_quote_versions_version_number"
        ),
        sa.ForeignKeyConstraint(
            ["quote_id"], ["quotes.id"],
            name="fk_quote_versions_quote_id", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name="fk_quote_versions_created_by_user_id", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_quote_versions"),
        sa.UniqueConstraint(
            "quote_id", "version_number", name="uq_quote_versions_quote_version"
        ),
    )
    op.create_index(
        "ix_quote_versions_quote_id", "quote_versions", ["quote_id"], unique=False
    )
    op.create_index(
        "ix_quote_versions_status", "quote_versions", ["status"], unique=False
    )

    # ------------------------------------------------------------------
    # quote_items
    # ------------------------------------------------------------------
    op.create_table(
        "quote_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("quote_version_id", sa.BigInteger(), nullable=False),
        sa.Column("request_item_id", sa.BigInteger(), nullable=False),
        sa.Column("variant_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="ck_quote_items_quantity"),
        sa.CheckConstraint("unit_price > 0", name="ck_quote_items_unit_price"),
        sa.CheckConstraint("total_price >= 0", name="ck_quote_items_total_price"),
        sa.ForeignKeyConstraint(
            ["quote_version_id"], ["quote_versions.id"],
            name="fk_quote_items_quote_version_id", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["request_item_id"], ["bulk_order_request_items.id"],
            name="fk_quote_items_request_item_id", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"], ["product_variants.id"],
            name="fk_quote_items_variant_id", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_quote_items"),
    )
    op.create_index(
        "ix_quote_items_quote_version_id", "quote_items", ["quote_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_quote_items_request_item_id", "quote_items", ["request_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_quote_items_request_item_id", table_name="quote_items")
    op.drop_index("ix_quote_items_quote_version_id", table_name="quote_items")
    op.drop_table("quote_items")

    op.drop_index("ix_quote_versions_status", table_name="quote_versions")
    op.drop_index("ix_quote_versions_quote_id", table_name="quote_versions")
    op.drop_table("quote_versions")

    op.drop_table("quotes")

    op.drop_index(
        "ix_bulk_order_request_items_product_id", table_name="bulk_order_request_items"
    )
    op.drop_index(
        "ix_bulk_order_request_items_request_id", table_name="bulk_order_request_items"
    )
    op.drop_table("bulk_order_request_items")

    op.drop_index("ix_bulk_order_requests_status", table_name="bulk_order_requests")
    op.drop_index(
        "ix_bulk_order_requests_customer_user_id", table_name="bulk_order_requests"
    )
    op.drop_table("bulk_order_requests")

    op.drop_table("bulk_customer_profiles")

    op.drop_constraint("ck_batches_purchase_price", "batches", type_="check")
    op.drop_constraint("ck_batches_supplier_or_wholesaler", "batches", type_="check")
    op.alter_column("batches", "wholesaler_user_id", nullable=False)
    op.drop_index("ix_batches_supplier_id", table_name="batches")
    op.drop_constraint("fk_batches_supplier_id", "batches", type_="foreignkey")
    op.drop_column("batches", "receiving_reference")
    op.drop_column("batches", "received_date")
    op.drop_column("batches", "purchase_currency")
    op.drop_column("batches", "purchase_price")
    op.drop_column("batches", "supplier_id")

    op.drop_index(
        "ix_supplier_evaluations_created_at", table_name="supplier_evaluations"
    )
    op.drop_index(
        "ix_supplier_evaluations_supplier_id", table_name="supplier_evaluations"
    )
    op.drop_table("supplier_evaluations")

    op.drop_index("ix_supplier_products_product_id", table_name="supplier_products")
    op.drop_index("ix_supplier_products_supplier_id", table_name="supplier_products")
    op.drop_table("supplier_products")

    op.drop_index("ix_suppliers_business_name", table_name="suppliers")
    op.drop_index("ix_suppliers_status", table_name="suppliers")
    op.drop_table("suppliers")
