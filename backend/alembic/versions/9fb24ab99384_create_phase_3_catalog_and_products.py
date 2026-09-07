"""create_phase_3_catalog_and_products

Revision ID: 9fb24ab99384
Revises: 56f5c455d612
Create Date: 2026-09-07 04:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9fb24ab99384"
down_revision: str | None = "56f5c455d612"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. categories
    op.create_table(
        "categories",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED')",
            name="ck_categories_status",
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_categories_parent_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["categories.id"],
            name="fk_categories_parent_id_categories",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
    )
    op.create_index(
        "ix_categories_parent_id", "categories", ["parent_id"], unique=False
    )
    op.create_index("ix_categories_status", "categories", ["status"], unique=False)

    # 2. products
    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'ARCHIVED')",
            name="ck_products_status",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_products_category_id_categories",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_products_slug"),
    )
    op.create_index(
        "ix_products_category_id", "products", ["category_id"], unique=False
    )
    op.create_index("ix_products_status", "products", ["status"], unique=False)

    # 3. product_variants
    op.create_table(
        "product_variants",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "unit IN ('KG', 'G', 'L', 'ML', 'UNIT', 'DOZEN', 'BOX', 'PACK')",
            name="ck_product_variants_unit",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_product_variants_quantity"),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED')",
            name="ck_product_variants_status",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_product_variants_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku", name="uq_product_variants_sku"),
    )
    op.create_index(
        "ix_product_variants_product_id",
        "product_variants",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        "ix_product_variants_status", "product_variants", ["status"], unique=False
    )

    # 4. product_images
    op.create_table(
        "product_images",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("alt_text", sa.String(length=255), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_product_images_sort_order",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_product_images_product_id_products",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_product_images_product_id", "product_images", ["product_id"], unique=False
    )
    op.create_index(
        "uq_product_images_product_primary",
        "product_images",
        ["product_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )

    # 5. prices
    op.create_table(
        "prices",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("variant_id", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("price > 0", name="ck_prices_price"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="ck_prices_valid_to",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name="fk_prices_variant_id_product_variants",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prices_variant_id", "prices", ["variant_id"], unique=False)
    op.create_index("ix_prices_valid_from", "prices", ["valid_from"], unique=False)
    op.create_index("ix_prices_is_active", "prices", ["is_active"], unique=False)

    # 6. Safety check and alter batches
    bind = op.get_bind()
    batch_count = bind.execute(sa.text("SELECT COUNT(*) FROM batches")).scalar()
    if batch_count and batch_count > 0:
        raise RuntimeError(
            f"Migration safety check failed: 'batches' table contains {batch_count} existing rows. "
            "A deterministic data migration is required before 'product_id' can be made NOT NULL."
        )

    op.add_column("batches", sa.Column("product_id", sa.BigInteger(), nullable=False))
    op.create_foreign_key(
        "fk_batches_product_id_products",
        "batches",
        "products",
        ["product_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_batches_product_id", "batches", ["product_id"], unique=False)


def downgrade() -> None:
    # 1. Reverse batches modifications
    op.drop_index("ix_batches_product_id", table_name="batches")
    op.drop_constraint(
        "fk_batches_product_id_products", table_name="batches", type_="foreignkey"
    )
    op.drop_column("batches", "product_id")

    # 2. Reverse prices
    op.drop_index("ix_prices_is_active", table_name="prices")
    op.drop_index("ix_prices_valid_from", table_name="prices")
    op.drop_index("ix_prices_variant_id", table_name="prices")
    op.drop_table("prices")

    # 3. Reverse product_images
    op.drop_index("uq_product_images_product_primary", table_name="product_images")
    op.drop_index("ix_product_images_product_id", table_name="product_images")
    op.drop_table("product_images")

    # 4. Reverse product_variants
    op.drop_index("ix_product_variants_status", table_name="product_variants")
    op.drop_index("ix_product_variants_product_id", table_name="product_variants")
    op.drop_table("product_variants")

    # 5. Reverse products
    op.drop_index("ix_products_status", table_name="products")
    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_table("products")

    # 6. Reverse categories
    op.drop_index("ix_categories_status", table_name="categories")
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_table("categories")
