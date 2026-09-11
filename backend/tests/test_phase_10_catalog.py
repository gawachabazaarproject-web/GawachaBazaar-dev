"""Phase 10 focused validation: public catalog browsing and ADMIN catalog management.

Fast-development-mode focused validation only (not a full regression run).
Covers: active-only public filtering, pagination, current-price selection,
401/403/admin-allowed authorization behavior (reusing Phase 9's
get_current_user/require_roles), primary-image handling, and clean 409/422
conflict behavior for duplicate slug/SKU and invalid enum values.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import ADMIN, CUSTOMER
from app.core.security import create_access_token, hash_password
from app.models.auth_session import AuthSession
from app.models.category import Category
from app.models.price import Price
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_or_create_role(db_session: Session, name: str) -> Role:
    role = db_session.query(Role).filter_by(name=name).first()
    if not role:
        role = Role(name=name, description=f"{name} role")
        db_session.add(role)
        db_session.commit()
        db_session.refresh(role)
    return role


def _create_user_with_role(
    db_session: Session, role_name: str, email: str
) -> User:
    user = User(
        name="Test User",
        email=email,
        phone=f"+9198{abs(hash(email)) % 100000000:08d}",
        password_hash=hash_password("SecurePass123"),
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.flush()

    role = _get_or_create_role(db_session, role_name)
    db_session.add(UserRole(user_id=user.id, role_id=role.id, is_primary=True))
    db_session.commit()
    db_session.refresh(user)
    return user


def _auth_headers(db_session: Session, user: User) -> dict[str, str]:
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=f"dummy-hash-{user.id}",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    token = create_access_token(user_id=user.id, session_id=session.id)
    return {"Authorization": f"Bearer {token}"}


def _create_category(
    db_session: Session, *, name: str = "Vegetables", slug: str = "vegetables", status: str = "ACTIVE", parent_id: int | None = None
) -> Category:
    category = Category(name=name, slug=slug, status=status, parent_id=parent_id)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def _create_product(
    db_session: Session, category: Category, *, name: str = "Fresh Tomato", slug: str = "fresh-tomato", status: str = "ACTIVE"
) -> Product:
    product = Product(
        category_id=category.id, name=name, slug=slug, status=status
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


def _create_variant(
    db_session: Session, product: Product, *, sku: str = "TOMATO-1KG", status: str = "ACTIVE", quantity: Decimal = Decimal("1.000")
) -> ProductVariant:
    variant = ProductVariant(
        product_id=product.id,
        name="1 KG",
        sku=sku,
        unit="KG",
        quantity=quantity,
        status=status,
    )
    db_session.add(variant)
    db_session.commit()
    db_session.refresh(variant)
    return variant


def _create_price(
    db_session: Session,
    variant: ProductVariant,
    *,
    price: Decimal = Decimal("40.00"),
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    is_active: bool = True,
) -> Price:
    row = Price(
        variant_id=variant.id,
        price=price,
        currency="INR",
        valid_from=valid_from or (datetime.now(UTC) - timedelta(days=1)),
        valid_to=valid_to,
        is_active=is_active,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Public catalog: active-only filtering
# ---------------------------------------------------------------------------


def test_1_public_category_list_returns_only_active(
    client: TestClient, db_session: Session
) -> None:
    _create_category(db_session, name="Active Cat", slug="active-cat", status="ACTIVE")
    _create_category(db_session, name="Inactive Cat", slug="inactive-cat", status="INACTIVE")
    _create_category(db_session, name="Archived Cat", slug="archived-cat", status="ARCHIVED")

    response = client.get("/api/v1/catalog/categories")

    assert response.status_code == 200
    body = response.json()
    names = {item["name"] for item in body["items"]}
    assert names == {"Active Cat"}
    assert body["total"] == 1


def test_2_public_category_detail_404_for_inactive(
    client: TestClient, db_session: Session
) -> None:
    inactive = _create_category(db_session, name="Hidden", slug="hidden", status="INACTIVE")

    response = client.get(f"/api/v1/catalog/categories/{inactive.id}")

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_3_public_product_list_active_only_and_category_filter(
    client: TestClient, db_session: Session
) -> None:
    cat_a = _create_category(db_session, name="Cat A", slug="cat-a")
    cat_b = _create_category(db_session, name="Cat B", slug="cat-b")
    _create_product(db_session, cat_a, name="Active Prod", slug="active-prod", status="ACTIVE")
    _create_product(db_session, cat_a, name="Draft Prod", slug="draft-prod", status="DRAFT")
    _create_product(db_session, cat_b, name="Other Cat Prod", slug="other-cat-prod", status="ACTIVE")

    response = client.get("/api/v1/catalog/products")
    body = response.json()
    names = {item["name"] for item in body["items"]}
    assert names == {"Active Prod", "Other Cat Prod"}

    filtered = client.get(f"/api/v1/catalog/products?category_id={cat_a.id}")
    filtered_names = {item["name"] for item in filtered.json()["items"]}
    assert filtered_names == {"Active Prod"}


def test_4_public_product_detail_excludes_inactive_variants_and_includes_price(
    client: TestClient, db_session: Session
) -> None:
    category = _create_category(db_session)
    product = _create_product(db_session, category)
    active_variant = _create_variant(db_session, product, sku="ACTIVE-SKU", status="ACTIVE")
    _create_variant(db_session, product, sku="ARCHIVED-SKU", status="ARCHIVED")
    _create_price(db_session, active_variant, price=Decimal("45.50"))

    response = client.get(f"/api/v1/catalog/products/{product.id}")

    assert response.status_code == 200
    body = response.json()
    skus = {v["sku"] for v in body["variants"]}
    assert skus == {"ACTIVE-SKU"}
    assert body["variants"][0]["current_price"]["price"] == "45.50"
    assert body["category"]["id"] == category.id


def test_5_current_price_selection_picks_most_recent_eligible(
    client: TestClient, db_session: Session
) -> None:
    category = _create_category(db_session)
    product = _create_product(db_session, category)
    variant = _create_variant(db_session, product)

    now = datetime.now(UTC)
    _create_price(
        db_session, variant, price=Decimal("30.00"),
        valid_from=now - timedelta(days=10), valid_to=now - timedelta(days=1),
    )  # expired
    _create_price(
        db_session, variant, price=Decimal("50.00"),
        valid_from=now + timedelta(days=10), valid_to=None,
    )  # future, not yet valid
    _create_price(
        db_session, variant, price=Decimal("40.00"),
        valid_from=now - timedelta(days=2), valid_to=None,
    )  # currently eligible, older
    _create_price(
        db_session, variant, price=Decimal("42.00"),
        valid_from=now - timedelta(hours=1), valid_to=None,
    )  # currently eligible, most recent -> expected winner

    response = client.get(f"/api/v1/catalog/products/{product.id}")

    current_price = response.json()["variants"][0]["current_price"]
    assert current_price["price"] == "42.00"


def test_6_pagination_metadata_and_max_page_size(
    client: TestClient, db_session: Session
) -> None:
    category = _create_category(db_session)
    for i in range(5):
        _create_product(db_session, category, name=f"Prod {i}", slug=f"prod-{i}")

    response = client.get("/api/v1/catalog/products?page=1&page_size=2")
    body = response.json()
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] == 5

    oversized = client.get("/api/v1/catalog/products?page_size=1000")
    assert oversized.status_code == 422


# ---------------------------------------------------------------------------
# Authorization: public vs CUSTOMER vs ADMIN
# ---------------------------------------------------------------------------


def test_7_admin_management_unauthenticated_returns_401(client: TestClient) -> None:
    response = client.post(
        "/api/v1/catalog/categories",
        json={"name": "New Cat", "slug": "new-cat"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_ERROR"


def test_8_admin_management_as_customer_returns_403(
    client: TestClient, db_session: Session
) -> None:
    customer = _create_user_with_role(db_session, CUSTOMER, "cust_catalog@example.com")
    headers = _auth_headers(db_session, customer)

    response = client.post(
        "/api/v1/catalog/categories",
        json={"name": "New Cat", "slug": "new-cat-2"},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "AUTHORIZATION_ERROR"


def test_9_admin_can_create_full_catalog_chain(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_catalog@example.com")
    headers = _auth_headers(db_session, admin)

    cat_resp = client.post(
        "/api/v1/catalog/categories",
        json={"name": "Fruits", "slug": "fruits"},
        headers=headers,
    )
    assert cat_resp.status_code == 201
    category_id = cat_resp.json()["id"]

    prod_resp = client.post(
        "/api/v1/catalog/products",
        json={
            "category_id": category_id,
            "name": "Banana",
            "slug": "banana",
            "status": "ACTIVE",
        },
        headers=headers,
    )
    assert prod_resp.status_code == 201
    product_id = prod_resp.json()["id"]

    variant_resp = client.post(
        f"/api/v1/catalog/products/{product_id}/variants",
        json={"name": "1 Dozen", "sku": "BANANA-DOZEN", "unit": "DOZEN", "quantity": "1"},
        headers=headers,
    )
    assert variant_resp.status_code == 201
    variant_id = variant_resp.json()["id"]

    price_resp = client.post(
        f"/api/v1/catalog/variants/{variant_id}/prices",
        json={"price": "60.00"},
        headers=headers,
    )
    assert price_resp.status_code == 201
    assert price_resp.json()["price"] == "60.00"

    image_resp = client.post(
        f"/api/v1/catalog/products/{product_id}/images",
        json={"image_url": "https://example.com/banana.jpg", "is_primary": True},
        headers=headers,
    )
    assert image_resp.status_code == 201
    assert image_resp.json()["is_primary"] is True


def test_10_duplicate_slug_returns_409(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_dup@example.com")
    headers = _auth_headers(db_session, admin)

    payload = {"name": "Grains", "slug": "grains"}
    first = client.post("/api/v1/catalog/categories", json=payload, headers=headers)
    assert first.status_code == 201

    second = client.post("/api/v1/catalog/categories", json=payload, headers=headers)
    assert second.status_code == 409
    assert second.json()["code"] == "CONFLICT_ERROR"


def test_11_invalid_status_and_unit_rejected(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_invalid@example.com")
    headers = _auth_headers(db_session, admin)

    bad_status = client.post(
        "/api/v1/catalog/categories",
        json={"name": "Bad", "slug": "bad-status", "status": "DELETED"},
        headers=headers,
    )
    assert bad_status.status_code == 422

    category = _create_category(db_session, name="UnitTest", slug="unit-test")
    product = _create_product(db_session, category, name="UnitProd", slug="unit-prod")
    bad_unit = client.post(
        f"/api/v1/catalog/products/{product.id}/variants",
        json={"name": "Bad Unit", "sku": "BAD-UNIT", "unit": "GALLON", "quantity": "1"},
        headers=headers,
    )
    assert bad_unit.status_code == 422


def test_12_primary_image_swap_unsets_previous_primary(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_img@example.com")
    headers = _auth_headers(db_session, admin)
    category = _create_category(db_session, name="ImgCat", slug="img-cat")
    product = _create_product(db_session, category, name="ImgProd", slug="img-prod")

    first = client.post(
        f"/api/v1/catalog/products/{product.id}/images",
        json={"image_url": "https://example.com/1.jpg", "is_primary": True},
        headers=headers,
    )
    first_id = first.json()["id"]
    assert first.json()["is_primary"] is True

    second = client.post(
        f"/api/v1/catalog/products/{product.id}/images",
        json={"image_url": "https://example.com/2.jpg", "is_primary": True},
        headers=headers,
    )
    assert second.status_code == 201
    assert second.json()["is_primary"] is True

    detail = client.get(f"/api/v1/catalog/products/{product.id}")
    images = detail.json()["images"]
    primary_flags = {img["id"]: img["is_primary"] for img in images}
    assert primary_flags[first_id] is False
    assert primary_flags[second.json()["id"]] is True


def test_13_existing_auth_routes_still_work(client: TestClient) -> None:
    """Smoke check that wiring the catalog router did not disturb /auth."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
