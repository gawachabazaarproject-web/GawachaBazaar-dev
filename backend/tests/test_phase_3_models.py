from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.category import Category
from app.models.farm import Farm
from app.models.price import Price
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.product_variant import ProductVariant
from app.models.user import User


def _create_user(
    db_session: Session,
    email: str = "farmer3@example.com",
    phone: str = "+919876543300",
) -> User:
    """Helper to create a valid user for testing."""
    user = User(
        name="Ramesh Patil",
        email=email,
        phone=phone,
        password_hash="hash",
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_farm(
    db_session: Session,
    owner_user_id: int,
    name: str = "Sahyadri Agro Farm",
) -> Farm:
    """Helper to create a valid farm for testing."""
    farm = Farm(
        owner_user_id=owner_user_id,
        name=name,
        address_line_1="Gat No 45",
        village="Narayangaon",
        city="Junnar",
        state="Maharashtra",
        postal_code="410504",
        latitude=Decimal("19.123456"),
        longitude=Decimal("73.987654"),
        contact_number="+919876543301",
        status="ACTIVE",
    )
    db_session.add(farm)
    db_session.commit()
    return farm


def _create_category(
    db_session: Session,
    name: str = "Vegetables",
    slug: str = "vegetables",
    parent_id: int | None = None,
    status: str = "ACTIVE",
    description: str | None = "Fresh farm vegetables",
) -> Category:
    """Helper to create a valid category for testing."""
    category = Category(
        name=name,
        slug=slug,
        parent_id=parent_id,
        status=status,
        description=description,
    )
    db_session.add(category)
    db_session.commit()
    return category


def _create_product(
    db_session: Session,
    category_id: int,
    name: str = "Desi Tomato",
    slug: str = "desi-tomato",
    status: str = "ACTIVE",
    description: str | None = "Naturally grown desi tomatoes",
) -> Product:
    """Helper to create a valid product for testing."""
    product = Product(
        category_id=category_id,
        name=name,
        slug=slug,
        status=status,
        description=description,
    )
    db_session.add(product)
    db_session.commit()
    return product


def _create_variant(
    db_session: Session,
    product_id: int,
    name: str = "1 KG Pack",
    sku: str = "TOM-DESI-1KG",
    unit: str = "KG",
    quantity: Decimal = Decimal("1.000"),
    status: str = "ACTIVE",
) -> ProductVariant:
    """Helper to create a valid product variant for testing."""
    variant = ProductVariant(
        product_id=product_id,
        name=name,
        sku=sku,
        unit=unit,
        quantity=quantity,
        status=status,
    )
    db_session.add(variant)
    db_session.commit()
    return variant


def _create_image(
    db_session: Session,
    product_id: int,
    image_url: str = "https://images.gawachabazaar.com/tomato.jpg",
    alt_text: str | None = "Ripe Desi Tomato",
    is_primary: bool = False,
    sort_order: int = 0,
) -> ProductImage:
    """Helper to create a valid product image for testing."""
    image = ProductImage(
        product_id=product_id,
        image_url=image_url,
        alt_text=alt_text,
        is_primary=is_primary,
        sort_order=sort_order,
    )
    db_session.add(image)
    db_session.commit()
    return image


def _create_price(
    db_session: Session,
    variant_id: int,
    price: Decimal = Decimal("45.00"),
    currency: str = "INR",
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    is_active: bool = True,
) -> Price:
    """Helper to create a valid price record for testing."""
    if valid_from is None:
        valid_from = datetime.now(UTC)
    price_obj = Price(
        variant_id=variant_id,
        price=price,
        currency=currency,
        valid_from=valid_from,
        valid_to=valid_to,
        is_active=is_active,
    )
    db_session.add(price_obj)
    db_session.commit()
    return price_obj


def _create_batch(
    db_session: Session,
    farm_id: int,
    product_id: int,
    batch_code: str = "BATCH-P3-001",
) -> Batch:
    """Helper to create a valid batch for testing."""
    batch = Batch(
        farm_id=farm_id,
        product_id=product_id,
        batch_code=batch_code,
        harvest_date=date(2026, 9, 7),
        expiry_date=date(2026, 9, 17),
        quantity=Decimal("150.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(batch)
    db_session.commit()
    return batch


# ==============================================================================
# CATEGORY TESTS (1-6)
# ==============================================================================


# 1. category can be created
def test_1_category_can_be_created(db_session: Session) -> None:
    cat = _create_category(db_session, name="Fruits", slug="fruits")

    assert cat.id is not None
    assert cat.name == "Fruits"
    assert cat.slug == "fruits"
    assert cat.status == "ACTIVE"
    assert cat.created_at is not None
    assert cat.updated_at is not None


# 2. root category can have parent_id NULL
def test_2_root_category_parent_id_null(db_session: Session) -> None:
    cat = _create_category(db_session, parent_id=None)

    assert cat.id is not None
    assert cat.parent_id is None
    assert cat.parent is None


# 3. child category can reference parent category
def test_3_child_category_references_parent(db_session: Session) -> None:
    parent = _create_category(db_session, name="Grains", slug="grains")
    child = _create_category(
        db_session, name="Rice", slug="rice", parent_id=parent.id
    )

    assert child.parent_id == parent.id
    assert child.parent.id == parent.id
    assert child in parent.children


# 4. category slug is unique
def test_4_category_slug_is_unique(db_session: Session) -> None:
    _create_category(db_session, name="Dairy 1", slug="dairy")

    duplicate_cat = Category(name="Dairy 2", slug="dairy", status="ACTIVE")
    db_session.add(duplicate_cat)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 5. category status accepts only ACTIVE/INACTIVE/ARCHIVED
def test_5_category_status_check(db_session: Session) -> None:
    for s in ["ACTIVE", "INACTIVE", "ARCHIVED"]:
        cat = _create_category(db_session, name=f"Cat {s}", slug=f"cat-{s.lower()}", status=s)
        assert cat.status == s

    invalid_cat = Category(
        name="Invalid Cat",
        slug="invalid-cat",
        status="DELETED",
    )
    db_session.add(invalid_cat)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 6. self-parenting category is rejected
def test_6_self_parenting_category_rejected(db_session: Session) -> None:
    cat = _create_category(db_session, name="Self Parent", slug="self-parent")

    cat.parent_id = cat.id
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ==============================================================================
# PRODUCT TESTS (7-10)
# ==============================================================================


# 7. product requires a valid category
def test_7_product_requires_valid_category(db_session: Session) -> None:
    # Non-existent category_id (FK violation)
    invalid_prod = Product(
        category_id=999999,
        name="Ghost Product",
        slug="ghost-prod",
        status="ACTIVE",
    )
    db_session.add(invalid_prod)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 8. product slug is unique
def test_8_product_slug_unique(db_session: Session) -> None:
    cat = _create_category(db_session)
    _create_product(db_session, category_id=cat.id, slug="unique-apple")

    dup_prod = Product(
        category_id=cat.id,
        name="Another Apple",
        slug="unique-apple",
        status="ACTIVE",
    )
    db_session.add(dup_prod)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 9. product status accepts only DRAFT/ACTIVE/INACTIVE/ARCHIVED
def test_9_product_status_check(db_session: Session) -> None:
    cat = _create_category(db_session)
    for s in ["DRAFT", "ACTIVE", "INACTIVE", "ARCHIVED"]:
        p = _create_product(
            db_session,
            category_id=cat.id,
            name=f"Prod {s}",
            slug=f"prod-{s.lower()}",
            status=s,
        )
        assert p.status == s

    invalid_prod = Product(
        category_id=cat.id,
        name="Invalid Prod",
        slug="invalid-prod",
        status="PUBLISHED",
    )
    db_session.add(invalid_prod)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 10. category can have multiple products
def test_10_category_can_have_multiple_products(db_session: Session) -> None:
    cat = _create_category(db_session)
    p1 = _create_product(db_session, category_id=cat.id, name="P1", slug="prod-p1")
    p2 = _create_product(db_session, category_id=cat.id, name="P2", slug="prod-p2")

    db_session.refresh(cat)
    assert len(cat.products) == 2
    assert {p.id for p in cat.products} == {p1.id, p2.id}


# ==============================================================================
# VARIANT TESTS (11-16)
# ==============================================================================


# 11. product can have multiple variants
def test_11_product_can_have_multiple_variants(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)

    v1 = _create_variant(db_session, product_id=prod.id, name="500g", sku="SKU-500G")
    v2 = _create_variant(db_session, product_id=prod.id, name="1kg", sku="SKU-1KG")

    db_session.refresh(prod)
    assert len(prod.variants) == 2
    assert {v.id for v in prod.variants} == {v1.id, v2.id}


# 12. SKU is globally unique
def test_12_sku_globally_unique(db_session: Session) -> None:
    cat = _create_category(db_session)
    p1 = _create_product(db_session, category_id=cat.id, slug="p1")
    p2 = _create_product(db_session, category_id=cat.id, slug="p2")

    _create_variant(db_session, product_id=p1.id, sku="GLOBAL-SKU-100")

    dup_variant = ProductVariant(
        product_id=p2.id,
        name="Another Variant",
        sku="GLOBAL-SKU-100",
        unit="KG",
        quantity=Decimal("1.000"),
        status="ACTIVE",
    )
    db_session.add(dup_variant)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 13. valid units are accepted
def test_13_valid_units_accepted(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)

    valid_units = ["KG", "G", "L", "ML", "UNIT", "DOZEN", "BOX", "PACK"]
    for idx, u in enumerate(valid_units):
        v = _create_variant(
            db_session,
            product_id=prod.id,
            name=f"Var {u}",
            sku=f"SKU-UNIT-{idx}",
            unit=u,
        )
        assert v.unit == u

    assert db_session.query(ProductVariant).count() == len(valid_units)


# 14. invalid unit is rejected
def test_14_invalid_unit_rejected(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)

    invalid_v = ProductVariant(
        product_id=prod.id,
        name="Invalid Unit Var",
        sku="SKU-INVALID-UNIT",
        unit="OUNCE",
        quantity=Decimal("1.000"),
        status="ACTIVE",
    )
    db_session.add(invalid_v)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 15. quantity must be greater than zero
def test_15_quantity_must_be_greater_than_zero(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)

    zero_v = ProductVariant(
        product_id=prod.id,
        name="Zero Quantity",
        sku="SKU-ZERO-QTY",
        unit="KG",
        quantity=Decimal("0.000"),
        status="ACTIVE",
    )
    db_session.add(zero_v)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    neg_v = ProductVariant(
        product_id=prod.id,
        name="Neg Quantity",
        sku="SKU-NEG-QTY",
        unit="KG",
        quantity=Decimal("-1.000"),
        status="ACTIVE",
    )
    db_session.add(neg_v)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 16. variant status constraint works
def test_16_variant_status_constraint(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)

    for idx, s in enumerate(["ACTIVE", "INACTIVE", "ARCHIVED"]):
        v = _create_variant(
            db_session,
            product_id=prod.id,
            sku=f"SKU-STATUS-{idx}",
            status=s,
        )
        assert v.status == s

    invalid_v = ProductVariant(
        product_id=prod.id,
        name="Invalid Status",
        sku="SKU-INVALID-STATUS",
        unit="KG",
        quantity=Decimal("1.000"),
        status="SUSPENDED",
    )
    db_session.add(invalid_v)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ==============================================================================
# IMAGE TESTS (17-21)
# ==============================================================================


# 17. product can have multiple images
def test_17_product_can_have_multiple_images(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)

    img1 = _create_image(db_session, product_id=prod.id, image_url="https://img.com/1.jpg")
    img2 = _create_image(db_session, product_id=prod.id, image_url="https://img.com/2.jpg")

    db_session.refresh(prod)
    assert len(prod.images) == 2
    assert {img.id for img in prod.images} == {img1.id, img2.id}


# 18. product can have only one primary image
def test_18_product_single_primary_image(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)

    _create_image(
        db_session,
        product_id=prod.id,
        image_url="https://img.com/primary1.jpg",
        is_primary=True,
    )

    dup_primary = ProductImage(
        product_id=prod.id,
        image_url="https://img.com/primary2.jpg",
        is_primary=True,
    )
    db_session.add(dup_primary)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 19. multiple non-primary images are allowed
def test_19_multiple_non_primary_images_allowed(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)

    img1 = _create_image(
        db_session, product_id=prod.id, image_url="https://img.com/a.jpg", is_primary=False
    )
    img2 = _create_image(
        db_session, product_id=prod.id, image_url="https://img.com/b.jpg", is_primary=False
    )
    img3 = _create_image(
        db_session, product_id=prod.id, image_url="https://img.com/c.jpg", is_primary=False
    )

    db_session.refresh(prod)
    assert len(prod.images) == 3
    assert all(not img.is_primary for img in [img1, img2, img3])


# 20. image sort_order cannot be negative
def test_20_image_sort_order_non_negative(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)

    invalid_img = ProductImage(
        product_id=prod.id,
        image_url="https://img.com/negative-sort.jpg",
        sort_order=-1,
    )
    db_session.add(invalid_img)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 21. deleting a product cascades to its images
def test_21_product_delete_cascades_to_images(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)
    img1 = _create_image(db_session, product_id=prod.id, image_url="https://img.com/c1.jpg")
    img2 = _create_image(db_session, product_id=prod.id, image_url="https://img.com/c2.jpg")

    prod_id = prod.id
    img1_id = img1.id
    img2_id = img2.id

    db_session.delete(prod)
    db_session.commit()

    assert db_session.query(Product).filter_by(id=prod_id).first() is None
    assert db_session.query(ProductImage).filter_by(id=img1_id).first() is None
    assert db_session.query(ProductImage).filter_by(id=img2_id).first() is None


# ==============================================================================
# PRICE TESTS (22-26)
# ==============================================================================


# 22. variant can have multiple price records
def test_22_variant_multiple_price_records(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)
    variant = _create_variant(db_session, product_id=prod.id)

    now = datetime.now(UTC)
    p1 = _create_price(
        db_session,
        variant_id=variant.id,
        price=Decimal("40.00"),
        valid_from=now - timedelta(days=30),
        valid_to=now,
        is_active=False,
    )
    p2 = _create_price(
        db_session,
        variant_id=variant.id,
        price=Decimal("45.00"),
        valid_from=now,
        valid_to=None,
        is_active=True,
    )

    db_session.refresh(variant)
    assert len(variant.prices) == 2
    assert {p.id for p in variant.prices} == {p1.id, p2.id}


# 23. price must be greater than zero
def test_23_price_greater_than_zero(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)
    variant = _create_variant(db_session, product_id=prod.id)

    zero_price = Price(
        variant_id=variant.id,
        price=Decimal("0.00"),
        currency="INR",
        valid_from=datetime.now(UTC),
    )
    db_session.add(zero_price)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    neg_price = Price(
        variant_id=variant.id,
        price=Decimal("-10.00"),
        currency="INR",
        valid_from=datetime.now(UTC),
    )
    db_session.add(neg_price)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 24. valid_to must be >= valid_from
def test_24_valid_to_ge_valid_from(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)
    variant = _create_variant(db_session, product_id=prod.id)

    now = datetime.now(UTC)
    invalid_price = Price(
        variant_id=variant.id,
        price=Decimal("50.00"),
        currency="INR",
        valid_from=now,
        valid_to=now - timedelta(days=1),
    )
    db_session.add(invalid_price)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 25. price currency is stored correctly
def test_25_price_currency_stored_correctly(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)
    variant = _create_variant(db_session, product_id=prod.id)

    price_inr = _create_price(
        db_session, variant_id=variant.id, price=Decimal("100.00"), currency="INR"
    )
    assert price_inr.currency == "INR"


# 26. price relationship to variant works
def test_26_price_relationship_to_variant(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)
    variant = _create_variant(db_session, product_id=prod.id)
    price = _create_price(db_session, variant_id=variant.id)

    assert price.variant.id == variant.id
    assert price in variant.prices


# ==============================================================================
# BATCH TRACEABILITY TESTS (27-30)
# ==============================================================================


# 27. batch can reference a product
def test_27_batch_references_product(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)

    batch = _create_batch(db_session, farm_id=farm.id, product_id=prod.id)

    assert batch.id is not None
    assert batch.product_id == prod.id
    assert batch.farm_id == farm.id


# 28. product can have multiple batches
def test_28_product_multiple_batches(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)

    b1 = _create_batch(
        db_session, farm_id=farm.id, product_id=prod.id, batch_code="BATCH-P3-A"
    )
    b2 = _create_batch(
        db_session, farm_id=farm.id, product_id=prod.id, batch_code="BATCH-P3-B"
    )

    db_session.refresh(prod)
    assert len(prod.batches) == 2
    assert {b.id for b in prod.batches} == {b1.id, b2.id}


# 29. batch requires a valid product
def test_29_batch_requires_valid_product(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)

    invalid_batch = Batch(
        farm_id=farm.id,
        product_id=999999,
        batch_code="BATCH-NO-PROD",
        harvest_date=date(2026, 9, 7),
        quantity=Decimal("10.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(invalid_batch)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 30. deleting a product referenced by a batch is restricted
def test_30_product_deletion_restricted_by_batch(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)
    _create_batch(db_session, farm_id=farm.id, product_id=prod.id)

    db_session.delete(prod)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ==============================================================================
# RELATIONSHIP TESTS (31-37)
# ==============================================================================


# 31. Category -> products
def test_31_relationship_category_to_products(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)

    db_session.refresh(cat)
    assert prod in cat.products


# 32. Product -> category
def test_32_relationship_product_to_category(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)

    assert prod.category.id == cat.id


# 33. Product -> variants
def test_33_relationship_product_to_variants(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)
    variant = _create_variant(db_session, product_id=prod.id)

    db_session.refresh(prod)
    assert variant in prod.variants
    assert variant.product.id == prod.id


# 34. Product -> images
def test_34_relationship_product_to_images(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)
    img = _create_image(db_session, product_id=prod.id)

    db_session.refresh(prod)
    assert img in prod.images
    assert img.product.id == prod.id


# 35. Product -> batches
def test_35_relationship_product_to_batches(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)
    batch = _create_batch(db_session, farm_id=farm.id, product_id=prod.id)

    db_session.refresh(prod)
    assert batch in prod.batches


# 36. Variant -> prices
def test_36_relationship_variant_to_prices(db_session: Session) -> None:
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)
    variant = _create_variant(db_session, product_id=prod.id)
    price = _create_price(db_session, variant_id=variant.id)

    db_session.refresh(variant)
    assert price in variant.prices
    assert price.variant.id == variant.id


# 37. Batch -> product
def test_37_relationship_batch_to_product(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, category_id=cat.id)
    batch = _create_batch(db_session, farm_id=farm.id, product_id=prod.id)

    assert batch.product.id == prod.id


# ==============================================================================
# SCHEMA INTROSPECTION TESTS (38-42)
# ==============================================================================


# 38. tables exist
def test_38_tables_exist(test_engine) -> None:
    inspector = inspect(test_engine)
    existing_tables = set(inspector.get_table_names())

    expected_tables = {
        "categories",
        "products",
        "product_variants",
        "product_images",
        "prices",
        "batches",
    }
    assert expected_tables.issubset(existing_tables), (
        f"Missing tables: {expected_tables - existing_tables}"
    )


# 39. expected foreign keys exist
def test_39_expected_foreign_keys(test_engine) -> None:
    inspector = inspect(test_engine)

    # categories.parent_id -> categories.id (RESTRICT)
    cat_fks = inspector.get_foreign_keys("categories")
    parent_fk = next((fk for fk in cat_fks if fk["constrained_columns"] == ["parent_id"]), None)
    assert parent_fk is not None
    assert parent_fk["referred_table"] == "categories"
    assert parent_fk["referred_columns"] == ["id"]
    assert parent_fk["options"].get("ondelete") == "RESTRICT"

    # products.category_id -> categories.id (RESTRICT)
    prod_fks = inspector.get_foreign_keys("products")
    cat_fk = next((fk for fk in prod_fks if fk["constrained_columns"] == ["category_id"]), None)
    assert cat_fk is not None
    assert cat_fk["referred_table"] == "categories"
    assert cat_fk["referred_columns"] == ["id"]
    assert cat_fk["options"].get("ondelete") == "RESTRICT"

    # product_variants.product_id -> products.id (RESTRICT)
    variant_fks = inspector.get_foreign_keys("product_variants")
    pv_prod_fk = next((fk for fk in variant_fks if fk["constrained_columns"] == ["product_id"]), None)
    assert pv_prod_fk is not None
    assert pv_prod_fk["referred_table"] == "products"
    assert pv_prod_fk["referred_columns"] == ["id"]
    assert pv_prod_fk["options"].get("ondelete") == "RESTRICT"

    # product_images.product_id -> products.id (CASCADE)
    img_fks = inspector.get_foreign_keys("product_images")
    img_prod_fk = next((fk for fk in img_fks if fk["constrained_columns"] == ["product_id"]), None)
    assert img_prod_fk is not None
    assert img_prod_fk["referred_table"] == "products"
    assert img_prod_fk["referred_columns"] == ["id"]
    assert img_prod_fk["options"].get("ondelete") == "CASCADE"

    # prices.variant_id -> product_variants.id (RESTRICT)
    price_fks = inspector.get_foreign_keys("prices")
    price_var_fk = next((fk for fk in price_fks if fk["constrained_columns"] == ["variant_id"]), None)
    assert price_var_fk is not None
    assert price_var_fk["referred_table"] == "product_variants"
    assert price_var_fk["referred_columns"] == ["id"]
    assert price_var_fk["options"].get("ondelete") == "RESTRICT"

    # batches.product_id -> products.id (RESTRICT)
    batch_fks = inspector.get_foreign_keys("batches")
    batch_prod_fk = next((fk for fk in batch_fks if fk["constrained_columns"] == ["product_id"]), None)
    assert batch_prod_fk is not None
    assert batch_prod_fk["referred_table"] == "products"
    assert batch_prod_fk["referred_columns"] == ["id"]
    assert batch_prod_fk["options"].get("ondelete") == "RESTRICT"


# 40. expected indexes exist
def test_40_expected_indexes(test_engine) -> None:
    inspector = inspect(test_engine)

    def get_index_names(table: str) -> set[str]:
        return {idx["name"] for idx in inspector.get_indexes(table)}

    assert "ix_categories_parent_id" in get_index_names("categories")
    assert "ix_categories_status" in get_index_names("categories")

    assert "ix_products_category_id" in get_index_names("products")
    assert "ix_products_status" in get_index_names("products")

    assert "ix_product_variants_product_id" in get_index_names("product_variants")
    assert "ix_product_variants_status" in get_index_names("product_variants")

    assert "ix_product_images_product_id" in get_index_names("product_images")

    assert "ix_prices_variant_id" in get_index_names("prices")
    assert "ix_prices_valid_from" in get_index_names("prices")
    assert "ix_prices_is_active" in get_index_names("prices")

    assert "ix_batches_product_id" in get_index_names("batches")


# 41. partial unique index for primary image exists
def test_41_partial_unique_index_primary_image(test_engine) -> None:
    inspector = inspect(test_engine)
    indexes = inspector.get_indexes("product_images")

    primary_idx = next(
        (idx for idx in indexes if idx["name"] == "uq_product_images_product_primary"),
        None,
    )
    assert primary_idx is not None, "Missing uq_product_images_product_primary index"
    assert primary_idx["unique"] is True
    assert primary_idx["column_names"] == ["product_id"]


# 42. unwanted tables such as inventory/orders/etc. do NOT exist
def test_42_unwanted_tables_do_not_exist(test_engine) -> None:
    inspector = inspect(test_engine)
    all_tables = set(inspector.get_table_names())

    unwanted_tables = {
        "inventory",
        "stock_movements",
        "warehouses",
        "carts",
        "orders",
        "order_items",
        "payments",
        "coupons",
        "promotions",
        "reviews",
        "delivery",
        "suppliers",
        "farmers",
        "procurement",
        "marketplace_vendors",
    }
    found_unwanted = unwanted_tables.intersection(all_tables)
    assert not found_unwanted, f"Unwanted tables detected in database: {found_unwanted}"
