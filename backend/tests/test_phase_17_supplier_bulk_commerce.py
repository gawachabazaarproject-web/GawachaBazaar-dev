"""Phase 17 focused validation: supplier management + bulk & custom commerce.

Fast-development-mode focused validation against real PostgreSQL.
Mutation tests re-read the database afterward, never trusting an HTTP
response alone.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import (
    ADMIN,
    CUSTOMER,
    DELIVERY_PARTNER,
    HUB_STAFF,
    OPERATIONS,
    WHOLESALER,
)
from app.core.security import create_access_token, hash_password
from app.models.address import Address
from app.models.auth_session import AuthSession
from app.models.batch import Batch
from app.models.bulk_order_request import BulkOrderRequest
from app.models.category import Category
from app.models.inventory_lot import InventoryLot
from app.models.inventory_reservation import InventoryReservation
from app.models.order import Order
from app.models.price import Price
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.quote import Quote
from app.models.quote_version import QuoteVersion
from app.models.role import Role
from app.models.supplier import Supplier
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


def _create_user_with_role(db_session: Session, role_name: str, email: str) -> User:
    user = User(
        name="Test User", email=email,
        phone=f"+9199{abs(hash(email)) % 100000000:08d}",
        password_hash=hash_password("SecurePass123"), status="ACTIVE",
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
        user_id=user.id, refresh_token_hash=f"dummy-hash-{user.id}-{user.email}",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    token = create_access_token(user_id=user.id, session_id=session.id)
    return {"Authorization": f"Bearer {token}"}


def _customer(db_session: Session, tag: str) -> tuple[User, dict[str, str]]:
    user = _create_user_with_role(db_session, CUSTOMER, f"cust17_{tag.lower()}@example.com")
    return user, _auth_headers(db_session, user)


def _staff(db_session: Session, role: str, tag: str) -> tuple[User, dict[str, str]]:
    user = _create_user_with_role(db_session, role, f"{role.lower()}17_{tag.lower()}@example.com")
    return user, _auth_headers(db_session, user)


def _create_product_variant(db_session: Session, *, tag: str) -> tuple[Product, ProductVariant]:
    category = Category(name=f"Cat17-{tag}", slug=f"cat17-{tag.lower()}", status="ACTIVE")
    db_session.add(category)
    db_session.commit()
    product = Product(
        category_id=category.id, name=f"Prod17-{tag}", slug=f"prod17-{tag.lower()}", status="ACTIVE"
    )
    db_session.add(product)
    db_session.commit()
    variant = ProductVariant(
        product_id=product.id, name="1 KG", sku=f"SKU17-{tag}", unit="KG",
        quantity=Decimal("1.000"), status="ACTIVE",
    )
    db_session.add(variant)
    db_session.commit()
    db_session.refresh(variant)
    return product, variant


def _create_price(db_session: Session, variant: ProductVariant, *, price: Decimal = Decimal("50.00")) -> None:
    db_session.add(
        Price(
            variant_id=variant.id, price=price, currency="INR",
            valid_from=datetime.now(UTC) - timedelta(days=1), valid_to=None, is_active=True,
        )
    )
    db_session.commit()


def _create_address(db_session: Session, user: User) -> Address:
    addr = Address(
        user_id=user.id, label="Home", address_line_1="221B Test Lane",
        city="Nagpur", state="Maharashtra", postal_code="440001",
    )
    db_session.add(addr)
    db_session.commit()
    db_session.refresh(addr)
    return addr


def _create_supplier(db_session: Session, *, tag: str) -> Supplier:
    supplier = Supplier(
        business_name=f"Supplier {tag}", status="ACTIVE",
        contact_person="Ravi Kumar", phone="+919800000000",
    )
    db_session.add(supplier)
    db_session.commit()
    db_session.refresh(supplier)
    return supplier


def _create_lot_for_supplier(
    db_session: Session, product: Product, variant: ProductVariant, supplier: Supplier,
    *, tag: str, quantity: Decimal = Decimal("100.000"),
) -> InventoryLot:
    """Creates a Batch sourced from `supplier` (Phase 17 path, no
    wholesaler_user_id) and one InventoryLot from it.
    """
    from app.models.inventory_location import InventoryLocation

    batch = Batch(
        supplier_id=supplier.id, product_id=product.id, batch_code=f"BATCH17-{tag}",
        harvest_date=date(2026, 1, 1), quantity=quantity, unit="KG", status="APPROVED",
        purchase_price=Decimal("25.00"), purchase_currency="INR",
        received_date=date(2026, 1, 2), receiving_reference=f"GRN-{tag}",
    )
    db_session.add(batch)
    db_session.commit()
    location = InventoryLocation(
        name=f"Hub17-{tag}", code=f"HUB17-{tag}", type="WAREHOUSE",
        address_line_1="1 Warehouse Rd", city="Nagpur", state="MH",
        postal_code="440001", status="ACTIVE",
    )
    db_session.add(location)
    db_session.commit()
    lot = InventoryLot(
        batch_id=batch.id, variant_id=variant.id, location_id=location.id,
        quantity=quantity, status="ACTIVE",
    )
    db_session.add(lot)
    db_session.commit()
    db_session.refresh(lot)
    return lot


def _ready_bulk_customer(db_session: Session, tag: str, *, stock: Decimal = Decimal("500.000")):
    """Customer + priced/stocked variant + address + a supplier the stock
    can be traced to, ready to submit a bulk request and eventually be
    quoted against a real, sellable variant.
    """
    user, headers = _customer(db_session, tag)
    product, variant = _create_product_variant(db_session, tag=tag)
    _create_price(db_session, variant, price=Decimal("40.00"))
    supplier = _create_supplier(db_session, tag=tag)
    lot = _create_lot_for_supplier(db_session, product, variant, supplier, tag=tag, quantity=stock)
    address = _create_address(db_session, user)
    return user, headers, product, variant, address, supplier, lot


# ---------------------------------------------------------------------------
# Batch/Supplier migration compatibility (1-5)
# ---------------------------------------------------------------------------


def test_1_batch_with_only_supplier_id_succeeds(client: TestClient, db_session: Session) -> None:
    _p, variant = _create_product_variant(db_session, tag="T1")
    supplier = _create_supplier(db_session, tag="T1")
    batch = Batch(
        supplier_id=supplier.id, product_id=variant.product_id, batch_code="BATCH-T1",
        harvest_date=date(2026, 1, 1), quantity=Decimal("10.000"), unit="KG", status="APPROVED",
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)
    assert batch.wholesaler_user_id is None
    assert batch.supplier_id == supplier.id


def test_2_legacy_batch_with_only_wholesaler_user_id_still_works(
    client: TestClient, db_session: Session
) -> None:
    """Backward compatibility: the Phase 8.1 path is untouched."""
    _p, variant = _create_product_variant(db_session, tag="T2")
    wholesaler = _create_user_with_role(db_session, WHOLESALER, "wholesaler17_t2@example.com")
    batch = Batch(
        wholesaler_user_id=wholesaler.id, product_id=variant.product_id, batch_code="BATCH-T2",
        harvest_date=date(2026, 1, 1), quantity=Decimal("10.000"), unit="KG", status="APPROVED",
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)
    assert batch.supplier_id is None
    assert batch.wholesaler_user_id == wholesaler.id


def test_3_batch_with_neither_supplier_nor_wholesaler_rejected(
    client: TestClient, db_session: Session
) -> None:
    from sqlalchemy.exc import IntegrityError

    _p, variant = _create_product_variant(db_session, tag="T3")
    batch = Batch(
        product_id=variant.product_id, batch_code="BATCH-T3",
        harvest_date=date(2026, 1, 1), quantity=Decimal("10.000"), unit="KG", status="APPROVED",
    )
    db_session.add(batch)
    try:
        db_session.commit()
        raised = False
    except IntegrityError:
        db_session.rollback()
        raised = True
    assert raised


def test_4_batch_procurement_fields_populated(client: TestClient, db_session: Session) -> None:
    _p, variant = _create_product_variant(db_session, tag="T4")
    supplier = _create_supplier(db_session, tag="T4")
    batch = Batch(
        supplier_id=supplier.id, product_id=variant.product_id, batch_code="BATCH-T4",
        harvest_date=date(2026, 1, 1), quantity=Decimal("10.000"), unit="KG", status="APPROVED",
        purchase_price=Decimal("22.50"), purchase_currency="INR",
        received_date=date(2026, 1, 3), receiving_reference="GRN-T4",
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)
    assert batch.purchase_price == Decimal("22.50")
    assert batch.receiving_reference == "GRN-T4"


def test_5_negative_purchase_price_rejected(client: TestClient, db_session: Session) -> None:
    from sqlalchemy.exc import IntegrityError

    _p, variant = _create_product_variant(db_session, tag="T5")
    supplier = _create_supplier(db_session, tag="T5")
    batch = Batch(
        supplier_id=supplier.id, product_id=variant.product_id, batch_code="BATCH-T5",
        harvest_date=date(2026, 1, 1), quantity=Decimal("10.000"), unit="KG", status="APPROVED",
        purchase_price=Decimal("-5.00"),
    )
    db_session.add(batch)
    try:
        db_session.commit()
        raised = False
    except IntegrityError:
        db_session.rollback()
        raised = True
    assert raised


# ---------------------------------------------------------------------------
# Supplier API (6-14)
# ---------------------------------------------------------------------------


def test_6_admin_can_create_and_get_supplier(client: TestClient, db_session: Session) -> None:
    _u, headers = _staff(db_session, ADMIN, "T6")
    response = client.post(
        "/api/v1/suppliers",
        json={"business_name": "Fresh Farms Co", "contact_person": "Amit", "phone": "+919812345678"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["business_name"] == "Fresh Farms Co"
    assert body["status"] == "ACTIVE"

    get_response = client.get(f"/api/v1/suppliers/{body['id']}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["business_name"] == "Fresh Farms Co"


def test_7_hub_staff_and_operations_can_manage_suppliers(
    client: TestClient, db_session: Session
) -> None:
    for role in (HUB_STAFF, OPERATIONS):
        _u, headers = _staff(db_session, role, f"T7{role}")
        response = client.post(
            "/api/v1/suppliers", json={"business_name": f"Supplier by {role}"}, headers=headers
        )
        assert response.status_code == 201, response.text


def test_8_customer_and_delivery_partner_cannot_access_suppliers(
    client: TestClient, db_session: Session
) -> None:
    supplier = _create_supplier(db_session, tag="T8")
    for role in (CUSTOMER, DELIVERY_PARTNER):
        _u, headers = (_customer(db_session, "T8") if role == CUSTOMER else _staff(db_session, role, "T8"))
        assert client.get("/api/v1/suppliers", headers=headers).status_code == 403
        assert client.get(f"/api/v1/suppliers/{supplier.id}", headers=headers).status_code == 403


def test_9_update_supplier(client: TestClient, db_session: Session) -> None:
    supplier = _create_supplier(db_session, tag="T9")
    _u, headers = _staff(db_session, ADMIN, "T9")
    response = client.patch(
        f"/api/v1/suppliers/{supplier.id}", json={"status": "INACTIVE"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "INACTIVE"


def test_10_link_product_to_supplier_and_list(client: TestClient, db_session: Session) -> None:
    _p, variant = _create_product_variant(db_session, tag="T10")
    supplier = _create_supplier(db_session, tag="T10")
    _u, headers = _staff(db_session, ADMIN, "T10")

    response = client.post(
        f"/api/v1/suppliers/{supplier.id}/products",
        json={"product_id": variant.product_id, "supplier_reference": "SUP-REF-1"},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["active"] is True

    listed = client.get(f"/api/v1/suppliers/{supplier.id}/products", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_11_duplicate_supplier_product_link_rejected(
    client: TestClient, db_session: Session
) -> None:
    _p, variant = _create_product_variant(db_session, tag="T11")
    supplier = _create_supplier(db_session, tag="T11")
    _u, headers = _staff(db_session, ADMIN, "T11")

    client.post(
        f"/api/v1/suppliers/{supplier.id}/products",
        json={"product_id": variant.product_id}, headers=headers,
    )
    second = client.post(
        f"/api/v1/suppliers/{supplier.id}/products",
        json={"product_id": variant.product_id}, headers=headers,
    )
    assert second.status_code == 409


def test_12_admin_only_can_create_supplier_evaluation(
    client: TestClient, db_session: Session
) -> None:
    supplier = _create_supplier(db_session, tag="T12")
    payload = {
        "quality_rating": "4.5", "delivery_rating": "4.0", "price_rating": "3.5",
        "reliability_rating": "4.8", "responsiveness_rating": "4.2", "overall_rating": "4.3",
        "notes": "Consistently good produce.",
    }
    _admin_user, admin_headers = _staff(db_session, ADMIN, "T12")
    response = client.post(
        f"/api/v1/suppliers/{supplier.id}/evaluations", json=payload, headers=admin_headers
    )
    assert response.status_code == 201
    assert response.json()["overall_rating"] == "4.3"

    _ops_user, ops_headers = _staff(db_session, OPERATIONS, "T12OPS")
    forbidden = client.post(
        f"/api/v1/suppliers/{supplier.id}/evaluations", json=payload, headers=ops_headers
    )
    assert forbidden.status_code == 403


def test_13_evaluation_history_is_append_only(client: TestClient, db_session: Session) -> None:
    supplier = _create_supplier(db_session, tag="T13")
    _u, headers = _staff(db_session, ADMIN, "T13")
    payload = {
        "quality_rating": "3.0", "delivery_rating": "3.0", "price_rating": "3.0",
        "reliability_rating": "3.0", "responsiveness_rating": "3.0", "overall_rating": "3.0",
    }
    client.post(f"/api/v1/suppliers/{supplier.id}/evaluations", json=payload, headers=headers)
    payload2 = {**payload, "overall_rating": "4.5"}
    client.post(f"/api/v1/suppliers/{supplier.id}/evaluations", json=payload2, headers=headers)

    history = client.get(f"/api/v1/suppliers/{supplier.id}/evaluations", headers=headers)
    assert history.json()["total"] == 2  # both preserved, neither overwritten


def test_14_supplier_performance_dashboard_data(client: TestClient, db_session: Session) -> None:
    product, variant = _create_product_variant(db_session, tag="T14")
    supplier = _create_supplier(db_session, tag="T14")
    _create_lot_for_supplier(db_session, product, variant, supplier, tag="T14A", quantity=Decimal("30.000"))
    _create_lot_for_supplier(db_session, product, variant, supplier, tag="T14B", quantity=Decimal("20.000"))
    _u, headers = _staff(db_session, ADMIN, "T14")
    client.post(
        f"/api/v1/suppliers/{supplier.id}/evaluations",
        json={
            "quality_rating": "4.0", "delivery_rating": "4.0", "price_rating": "4.0",
            "reliability_rating": "4.0", "responsiveness_rating": "4.0", "overall_rating": "4.0",
        },
        headers=headers,
    )

    response = client.get(f"/api/v1/suppliers/{supplier.id}/performance", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_batches_supplied"] == 2
    assert body["supply_summary"][0]["total_quantity_supplied"] == "50.000"
    assert body["evaluation_count"] == 1
    assert body["average_ratings"]["overall"] == "4.0"


# ---------------------------------------------------------------------------
# Bulk customer profile (15)
# ---------------------------------------------------------------------------


def test_15_upsert_bulk_customer_profile(client: TestClient, db_session: Session) -> None:
    _u, headers = _customer(db_session, "T15")
    response = client.put(
        "/api/v1/bulk-orders/profile",
        json={"business_name": "Nagpur Grand Hotel", "business_type": "HOTEL"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["business_type"] == "HOTEL"

    update = client.put(
        "/api/v1/bulk-orders/profile",
        json={"business_name": "Nagpur Grand Hotel", "business_type": "CATERER"},
        headers=headers,
    )
    assert update.status_code == 200
    assert update.json()["business_type"] == "CATERER"

    get_response = client.get("/api/v1/bulk-orders/profile", headers=headers)
    assert get_response.json()["business_type"] == "CATERER"


# ---------------------------------------------------------------------------
# Bulk order request creation - never an Order (16-20)
# ---------------------------------------------------------------------------


def test_16_mode_a_catalog_product_request_creates_no_order(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, _product, variant, address, _supplier, _lot = _ready_bulk_customer(
        db_session, "T16"
    )
    response = client.post(
        "/api/v1/bulk-orders/requests",
        json={
            "address_id": address.id,
            "items": [
                {"product_id": variant.product_id, "requested_quantity": "100", "unit": "KG"}
            ],
        },
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "REQUESTED"
    assert body["items"][0]["product_name"] is not None

    db_session.expire_all()
    assert db_session.query(Order).count() == 0
    assert db_session.query(InventoryReservation).count() == 0


def test_17_mode_b_custom_item_request(client: TestClient, db_session: Session) -> None:
    _user, headers, _product, _variant, address, _supplier, _lot = _ready_bulk_customer(
        db_session, "T17"
    )
    response = client.post(
        "/api/v1/bulk-orders/requests",
        json={
            "address_id": address.id,
            "customer_notes": "Medium tomatoes, no damaged produce.",
            "items": [
                {"custom_item_name": "Heirloom Tomatoes", "requested_quantity": "150", "unit": "KG"}
            ],
        },
        headers=headers,
    )
    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["custom_item_name"] == "Heirloom Tomatoes"
    assert item["product_id"] is None


def test_18_item_with_both_product_and_custom_name_rejected(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, _product, variant, address, _supplier, _lot = _ready_bulk_customer(
        db_session, "T18"
    )
    response = client.post(
        "/api/v1/bulk-orders/requests",
        json={
            "address_id": address.id,
            "items": [
                {
                    "product_id": variant.product_id, "custom_item_name": "Also custom",
                    "requested_quantity": "10", "unit": "KG",
                }
            ],
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_19_item_with_neither_product_nor_custom_name_rejected(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, *_rest = _ready_bulk_customer(db_session, "T19")
    response = client.post(
        "/api/v1/bulk-orders/requests",
        json={"items": [{"requested_quantity": "10", "unit": "KG"}]},
        headers=headers,
    )
    assert response.status_code == 422


def test_20_customer_cannot_see_another_customers_request(
    client: TestClient, db_session: Session
) -> None:
    _user_a, headers_a, _p, variant, address, _s, _lot = _ready_bulk_customer(db_session, "T20A")
    created = client.post(
        "/api/v1/bulk-orders/requests",
        json={
            "address_id": address.id,
            "items": [{"product_id": variant.product_id, "requested_quantity": "10", "unit": "KG"}],
        },
        headers=headers_a,
    ).json()

    _user_b, headers_b = _customer(db_session, "T20B")
    response = client.get(f"/api/v1/bulk-orders/requests/{created['id']}", headers=headers_b)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Request lifecycle + quoting (21-28)
# ---------------------------------------------------------------------------


def _create_request(
    client: TestClient, headers: dict, address, variant: ProductVariant, qty: str = "100"
) -> dict:
    response = client.post(
        "/api/v1/bulk-orders/requests",
        json={
            "address_id": address.id,
            "items": [{"product_id": variant.product_id, "requested_quantity": qty, "unit": "KG"}],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _draft_and_send(
    client: TestClient, admin_headers: dict, request_id: int, item_id: int, variant_id: int,
    *, quantity: str = "100", unit_price: str = "35.00",
) -> dict:
    """Drafts a quote version and immediately sends it - the common path
    most tests need; a few tests exercise DRAFT-vs-SENT directly instead.
    """
    draft = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request_id}/quote",
        json={"items": [{"request_item_id": item_id, "variant_id": variant_id, "quantity": quantity, "unit_price": unit_price}]},
        headers=admin_headers,
    )
    assert draft.status_code == 201, draft.text
    version_id = draft.json()["versions"][-1]["id"]
    sent = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request_id}/quote/{version_id}/send",
        headers=admin_headers,
    )
    assert sent.status_code == 200, sent.text
    return sent.json()


def test_21_admin_review_transitions_requested_to_under_review(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(db_session, "T21")
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "T21")

    response = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/review",
        json={"admin_notes": "Looks reasonable, checking stock."},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "UNDER_REVIEW"
    assert response.json()["admin_notes"] == "Looks reasonable, checking stock."


def test_22_draft_then_send_moves_request_to_quoted(client: TestClient, db_session: Session) -> None:
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(db_session, "T22")
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "T22")
    client.post(f"/api/v1/bulk-orders/admin/requests/{request['id']}/review", json={}, headers=admin_headers)

    item_id = request["items"][0]["id"]
    draft = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/quote",
        json={
            "currency": "INR",
            "items": [
                {
                    "request_item_id": item_id, "variant_id": variant.id,
                    "quantity": "100", "unit_price": "35.00",
                }
            ],
        },
        headers=admin_headers,
    )
    assert draft.status_code == 201
    body = draft.json()
    assert body["versions"][0]["version_number"] == 1
    assert body["versions"][0]["status"] == "DRAFT"
    assert body["versions"][0]["items"][0]["total_price"] == "3500.00"

    # A DRAFT is not yet visible/actionable - request stays UNDER_REVIEW.
    still_reviewing = client.get(f"/api/v1/bulk-orders/requests/{request['id']}", headers=headers)
    assert still_reviewing.json()["status"] == "UNDER_REVIEW"

    version_id = body["versions"][0]["id"]
    sent = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/quote/{version_id}/send",
        headers=admin_headers,
    )
    assert sent.status_code == 200
    assert sent.json()["versions"][0]["status"] == "SENT"

    detail = client.get(f"/api/v1/bulk-orders/requests/{request['id']}", headers=headers)
    assert detail.json()["status"] == "QUOTED"


def test_23_requoting_supersedes_but_preserves_old_version(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(db_session, "T23")
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "T23")
    item_id = request["items"][0]["id"]

    first = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/quote",
        json={"items": [{"request_item_id": item_id, "variant_id": variant.id, "quantity": "100", "unit_price": "35.00"}]},
        headers=admin_headers,
    ).json()
    first_version_id = first["versions"][0]["id"]
    client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/quote/{first_version_id}/send",
        headers=admin_headers,
    )

    second_draft = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/quote",
        json={"items": [{"request_item_id": item_id, "variant_id": variant.id, "quantity": "100", "unit_price": "33.00"}]},
        headers=admin_headers,
    ).json()
    # Drafting a revision does NOT yet touch the still-SENT first version.
    assert second_draft["versions"][0]["status"] == "SENT"
    assert second_draft["versions"][1]["status"] == "DRAFT"

    second_version_id = second_draft["versions"][1]["id"]
    sent_second = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/quote/{second_version_id}/send",
        headers=admin_headers,
    )
    assert sent_second.status_code == 200
    versions = sent_second.json()["versions"]
    assert len(versions) == 2  # nothing destroyed
    assert versions[0]["version_number"] == 1
    assert versions[0]["status"] == "SUPERSEDED"
    assert versions[0]["items"][0]["unit_price"] == "35.00"  # old price preserved
    assert versions[1]["version_number"] == 2
    assert versions[1]["status"] == "SENT"
    assert versions[1]["items"][0]["unit_price"] == "33.00"


def test_24_customer_accept_targets_current_active_version(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(db_session, "T24")
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "T24")
    item_id = request["items"][0]["id"]
    _draft_and_send(client, admin_headers, request["id"], item_id, variant.id)

    response = client.post(
        f"/api/v1/bulk-orders/requests/{request['id']}/accept", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "CUSTOMER_ACCEPTED"

    db_session.expire_all()
    assert db_session.query(Order).count() == 0  # accept alone still creates no Order


def test_25_cannot_accept_without_a_quote(client: TestClient, db_session: Session) -> None:
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(db_session, "T25")
    request = _create_request(client, headers, address, variant)
    response = client.post(
        f"/api/v1/bulk-orders/requests/{request['id']}/accept", headers=headers
    )
    assert response.status_code == 409


def test_26_customer_can_cancel_own_request(client: TestClient, db_session: Session) -> None:
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(db_session, "T26")
    request = _create_request(client, headers, address, variant)
    response = client.post(
        f"/api/v1/bulk-orders/requests/{request['id']}/cancel", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


def test_27_cannot_cancel_already_converted_request(client: TestClient, db_session: Session) -> None:
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(db_session, "T27", stock=Decimal("500"))
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "T27")
    item_id = request["items"][0]["id"]
    _draft_and_send(client, admin_headers, request["id"], item_id, variant.id)
    client.post(f"/api/v1/bulk-orders/requests/{request['id']}/accept", headers=headers)
    client.post(f"/api/v1/bulk-orders/admin/requests/{request['id']}/convert", headers=admin_headers)

    response = client.post(f"/api/v1/bulk-orders/requests/{request['id']}/cancel", headers=headers)
    assert response.status_code == 409


def test_28_operations_cannot_review_as_hub_staff(client: TestClient, db_session: Session) -> None:
    """HUB_STAFF is deliberately excluded from bulk/custom commerce
    review+quoting - it is a commercial decision, not a warehouse task."""
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(db_session, "T28")
    request = _create_request(client, headers, address, variant)
    _hub, hub_headers = _staff(db_session, HUB_STAFF, "T28")
    response = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/review", json={}, headers=hub_headers
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Conversion to a real Order (29-34)
# ---------------------------------------------------------------------------


def _quote_accept(
    client: TestClient, admin_headers: dict, customer_headers: dict, request: dict,
    variant: ProductVariant, *, quantity: str = "100", unit_price: str = "35.00",
) -> None:
    item_id = request["items"][0]["id"]
    _draft_and_send(
        client, admin_headers, request["id"], item_id, variant.id,
        quantity=quantity, unit_price=unit_price,
    )
    client.post(f"/api/v1/bulk-orders/requests/{request['id']}/accept", headers=customer_headers)


def test_29_convert_creates_real_order_and_reservation(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, _p, variant, address, _s, lot = _ready_bulk_customer(
        db_session, "T29", stock=Decimal("500")
    )
    request = _create_request(client, headers, address, variant, qty="100")
    _admin, admin_headers = _staff(db_session, ADMIN, "T29")
    _quote_accept(client, admin_headers, headers, request, variant)

    response = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/convert", headers=admin_headers
    )
    assert response.status_code == 201
    order_body = response.json()
    assert order_body["status"] == "PENDING"
    assert order_body["total_amount"] == "3500.00"
    assert len(order_body["items"]) == 1
    assert order_body["items"][0]["quantity"] == "100.000"

    db_session.expire_all()
    order = db_session.query(Order).filter_by(id=order_body["id"]).one()
    assert order.user_id == _user.id
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order.id).one()
    assert reservation.status == "ACTIVE"
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity == Decimal("100.000")

    detail = client.get(f"/api/v1/bulk-orders/requests/{request['id']}", headers=headers)
    assert detail.json()["status"] == "CONVERTED_TO_ORDER"


def test_30_converted_order_can_be_paid_via_cod_like_any_retail_order(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(
        db_session, "T30", stock=Decimal("500")
    )
    request = _create_request(client, headers, address, variant, qty="50")
    _admin, admin_headers = _staff(db_session, ADMIN, "T30")
    _quote_accept(client, admin_headers, headers, request, variant, quantity="50")
    order = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/convert", headers=admin_headers
    ).json()

    payment = client.post(
        "/api/v1/payments", json={"order_id": order["id"], "payment_method": "COD"}, headers=headers
    )
    assert payment.status_code == 201

    db_session.expire_all()
    refreshed_order = db_session.get(Order, order["id"])
    assert refreshed_order.status == "CONFIRMED"
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    assert reservation.status == "COMMITTED"


def test_31_cannot_convert_before_customer_accepts(client: TestClient, db_session: Session) -> None:
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(db_session, "T31")
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "T31")
    item_id = request["items"][0]["id"]
    client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/quote",
        json={"items": [{"request_item_id": item_id, "variant_id": variant.id, "quantity": "100", "unit_price": "35.00"}]},
        headers=admin_headers,
    )
    response = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/convert", headers=admin_headers
    )
    assert response.status_code == 409


def test_32_insufficient_stock_at_conversion_rolls_back_cleanly(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, _p, variant, address, _s, lot = _ready_bulk_customer(
        db_session, "T32", stock=Decimal("10")
    )
    request = _create_request(client, headers, address, variant, qty="100")
    _admin, admin_headers = _staff(db_session, ADMIN, "T32")
    # Quote MORE than is physically available - conversion must fail.
    _quote_accept(client, admin_headers, headers, request, variant, quantity="100")

    response = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/convert", headers=admin_headers
    )
    assert response.status_code == 409

    db_session.expire_all()
    assert db_session.query(Order).count() == 0
    assert db_session.query(InventoryReservation).count() == 0
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity == Decimal("0.000")
    detail = client.get(f"/api/v1/bulk-orders/requests/{request['id']}", headers=headers)
    assert detail.json()["status"] == "CUSTOMER_ACCEPTED"  # left retryable, not corrupted


def test_33_customer_cannot_convert_their_own_request(client: TestClient, db_session: Session) -> None:
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(
        db_session, "T33", stock=Decimal("500")
    )
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "T33")
    _quote_accept(client, admin_headers, headers, request, variant)

    response = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/convert", headers=headers
    )
    assert response.status_code == 403


def test_34_conversion_without_address_rejected(client: TestClient, db_session: Session) -> None:
    _user, headers, _p, variant, _address, _s, _lot = _ready_bulk_customer(
        db_session, "T34", stock=Decimal("500")
    )
    request = client.post(
        "/api/v1/bulk-orders/requests",
        json={"items": [{"product_id": variant.product_id, "requested_quantity": "10", "unit": "KG"}]},
        headers=headers,
    ).json()
    _admin, admin_headers = _staff(db_session, ADMIN, "T34")
    _quote_accept(client, admin_headers, headers, request, variant, quantity="10")

    response = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/convert", headers=admin_headers
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# send/reject endpoints, expiry, availability, order_id backstop (35-39)
# ---------------------------------------------------------------------------


def test_35_reject_quote_version_endpoint(client: TestClient, db_session: Session) -> None:
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(db_session, "T35")
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "T35")
    item_id = request["items"][0]["id"]
    sent = _draft_and_send(client, admin_headers, request["id"], item_id, variant.id)
    version_id = sent["versions"][0]["id"]

    response = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/quote/{version_id}/reject",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["versions"][0]["status"] == "REJECTED"

    # A rejected version can no longer be accepted by the customer.
    accept = client.post(f"/api/v1/bulk-orders/requests/{request['id']}/accept", headers=headers)
    assert accept.status_code == 409


def test_36_draft_cannot_be_sent_twice(client: TestClient, db_session: Session) -> None:
    """Once SENT, that same version cannot be sent again - resending must
    go through a brand-new draft version instead."""
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(db_session, "T36")
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "T36")
    item_id = request["items"][0]["id"]
    sent = _draft_and_send(client, admin_headers, request["id"], item_id, variant.id)
    version_id = sent["versions"][0]["id"]

    response = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/quote/{version_id}/send",
        headers=admin_headers,
    )
    assert response.status_code == 409


def test_37_expired_quote_cannot_be_accepted_and_is_lazily_marked_expired(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(db_session, "T37")
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "T37")
    item_id = request["items"][0]["id"]
    sent = _draft_and_send(client, admin_headers, request["id"], item_id, variant.id)
    version_id = sent["versions"][0]["id"]

    # Backdate valid_until directly - the API never lets a client submit
    # an already-past expiry, so this simulates time passing.
    version = db_session.get(QuoteVersion, version_id)
    version.valid_until = date.today() - timedelta(days=1)
    db_session.commit()

    response = client.post(f"/api/v1/bulk-orders/requests/{request['id']}/accept", headers=headers)
    assert response.status_code == 409

    db_session.expire_all()
    assert db_session.get(QuoteVersion, version_id).status == "EXPIRED"

    # The expiry is sticky - retrying does not resurrect or re-derive a
    # different outcome.
    retry = client.post(f"/api/v1/bulk-orders/requests/{request['id']}/accept", headers=headers)
    assert retry.status_code == 409


def test_38_variant_availability_is_read_only_and_never_reserves(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, _p, variant, address, _s, lot = _ready_bulk_customer(
        db_session, "T38", stock=Decimal("60")
    )
    _admin, admin_headers = _staff(db_session, ADMIN, "T38")

    response = client.get(
        f"/api/v1/bulk-orders/admin/variants/{variant.id}/availability", headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["variant_id"] == variant.id
    assert body["total_quantity"] == "60.000"
    assert body["reserved_quantity"] == "0.000"
    assert body["available_quantity"] == "60.000"

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity == Decimal("0.000")  # never touched
    assert db_session.query(InventoryReservation).count() == 0  # no reservation created


def test_39_order_id_backstop_set_after_conversion_and_unique(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(
        db_session, "T39", stock=Decimal("500")
    )
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "T39")
    _quote_accept(client, admin_headers, headers, request, variant)

    order = client.post(
        f"/api/v1/bulk-orders/admin/requests/{request['id']}/convert", headers=admin_headers
    ).json()

    db_session.expire_all()
    request_row = db_session.get(BulkOrderRequest, request["id"])
    assert request_row.order_id == order["id"]

    # The DB uniqueness backstop rejects a second request row from ever
    # pointing at the same order.
    from sqlalchemy.exc import IntegrityError

    other_user, other_headers = _customer(db_session, "T39B")
    other_address = _create_address(db_session, other_user)
    dupe = BulkOrderRequest(
        customer_user_id=other_user.id, address_id=other_address.id,
        status="CONVERTED_TO_ORDER", order_id=order["id"],
    )
    db_session.add(dupe)
    try:
        db_session.commit()
        raised = False
    except IntegrityError:
        db_session.rollback()
        raised = True
    assert raised


# ---------------------------------------------------------------------------
# Concurrency - real threads, real PostgreSQL row locks (40-45)
# ---------------------------------------------------------------------------


def test_concurrency_40_two_accept_attempts_on_the_same_quote_exactly_one_effect(
    client: TestClient, db_session: Session
) -> None:
    """(A) Two concurrent accept attempts on the same SENT quote must not
    corrupt state - `_lock_request` serializes them on the request row, so
    the loser re-reads status=CUSTOMER_ACCEPTED post-lock and gets a
    controlled 409 rather than a second acceptance (an acceptable outcome
    per the spec's "safe idempotent OR controlled conflict" rule)."""
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(
        db_session, "C40", stock=Decimal("500")
    )
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "C40")
    item_id = request["items"][0]["id"]
    _draft_and_send(client, admin_headers, request["id"], item_id, variant.id)

    def accept():
        return client.post(f"/api/v1/bulk-orders/requests/{request['id']}/accept", headers=headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(accept)
        f2 = pool.submit(accept)
        r1, r2 = f1.result(), f2.result()

    assert sorted([r1.status_code, r2.status_code]) == [200, 409]  # exactly one acceptance wins
    db_session.expire_all()
    request_row = db_session.get(BulkOrderRequest, request["id"])
    assert request_row.status == "CUSTOMER_ACCEPTED"
    quote = db_session.query(Quote).filter_by(request_id=request["id"]).one()
    sent_versions = (
        db_session.query(QuoteVersion)
        .filter_by(quote_id=quote.id, status="ACCEPTED")
        .all()
    )
    assert len(sent_versions) == 1  # exactly one version ends up ACCEPTED, never two


def test_concurrency_41_duplicate_conversion_requests_create_exactly_one_order(
    client: TestClient, db_session: Session
) -> None:
    """(B) Two concurrent conversion requests for the same accepted
    request must create exactly one Order - the DB uniqueness backstop
    on bulk_order_requests.order_id defends this alongside the row lock."""
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(
        db_session, "C41", stock=Decimal("500")
    )
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "C41")
    _quote_accept(client, admin_headers, headers, request, variant)

    def convert():
        return client.post(
            f"/api/v1/bulk-orders/admin/requests/{request['id']}/convert", headers=admin_headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(convert)
        f2 = pool.submit(convert)
        r1, r2 = f1.result(), f2.result()

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [201, 409]  # exactly one conversion wins

    db_session.expire_all()
    request_row = db_session.get(BulkOrderRequest, request["id"])
    assert request_row.order_id is not None
    assert db_session.query(Order).filter_by(user_id=_user.id).count() == 1


def test_concurrency_42_two_bulk_orders_competing_for_limited_stock_no_oversell(
    client: TestClient, db_session: Session
) -> None:
    """(C) Two different accepted bulk requests converting concurrently
    and competing for the same limited inventory lot must never oversell -
    one wins, the other gets a clean 409 with no partial reservation."""
    _p, variant = _create_product_variant(db_session, tag="C42")
    _create_price(db_session, variant, price=Decimal("40.00"))
    supplier = _create_supplier(db_session, tag="C42")
    lot = _create_lot_for_supplier(
        db_session, variant.product, variant, supplier, tag="C42", quantity=Decimal("100")
    )

    user_a, headers_a = _customer(db_session, "C42A")
    address_a = _create_address(db_session, user_a)
    user_b, headers_b = _customer(db_session, "C42B")
    address_b = _create_address(db_session, user_b)
    _admin, admin_headers = _staff(db_session, ADMIN, "C42")

    request_a = _create_request(client, headers_a, address_a, variant, qty="80")
    request_b = _create_request(client, headers_b, address_b, variant, qty="80")
    _quote_accept(client, admin_headers, headers_a, request_a, variant, quantity="80")
    _quote_accept(client, admin_headers, headers_b, request_b, variant, quantity="80")

    def convert(request_id: int):
        return client.post(
            f"/api/v1/bulk-orders/admin/requests/{request_id}/convert", headers=admin_headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(convert, request_a["id"])
        f2 = pool.submit(convert, request_b["id"])
        r1, r2 = f1.result(), f2.result()

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [201, 409]  # only 100 units exist for two 80-unit requests

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity <= Decimal("100.000")  # never oversold
    assert db_session.query(Order).count() == 1


def test_concurrency_43_concurrent_supplier_updates_no_lost_update(
    client: TestClient, db_session: Session
) -> None:
    """(D) Two concurrent PATCHes to different fields on the same
    supplier must not lose either write - the row lock added to
    update_supplier serializes them."""
    supplier = _create_supplier(db_session, tag="C43")
    _admin, admin_headers = _staff(db_session, ADMIN, "C43")

    def patch_phone():
        return client.patch(
            f"/api/v1/suppliers/{supplier.id}", json={"phone": "+919811111111"}, headers=admin_headers
        )

    def patch_notes():
        return client.patch(
            f"/api/v1/suppliers/{supplier.id}", json={"notes": "Reliable, fast turnaround"}, headers=admin_headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(patch_phone)
        f2 = pool.submit(patch_notes)
        r1, r2 = f1.result(), f2.result()

    assert r1.status_code == 200 and r2.status_code == 200

    db_session.expire_all()
    refreshed = db_session.get(Supplier, supplier.id)
    assert refreshed.phone == "+919811111111"  # both writes survived
    assert refreshed.notes == "Reliable, fast turnaround"


def test_concurrency_44_accept_races_expiry_exactly_one_terminal_outcome(
    client: TestClient, db_session: Session
) -> None:
    """(E) Accept attempts racing an already-past expiry must settle on
    exactly one deterministic terminal outcome - either accepted (if the
    lock-holder's expiry check runs before the deadline is applied) is
    not possible here since valid_until is already in the past before
    either thread starts, so both must observe expiry and the version
    must end EXPIRED, never ACCEPTED."""
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(db_session, "C44")
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "C44")
    item_id = request["items"][0]["id"]
    sent = _draft_and_send(client, admin_headers, request["id"], item_id, variant.id)
    version_id = sent["versions"][0]["id"]

    version = db_session.get(QuoteVersion, version_id)
    version.valid_until = date.today() - timedelta(days=1)
    db_session.commit()

    def accept():
        return client.post(f"/api/v1/bulk-orders/requests/{request['id']}/accept", headers=headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(accept)
        f2 = pool.submit(accept)
        r1, r2 = f1.result(), f2.result()

    assert r1.status_code == 409 and r2.status_code == 409

    db_session.expire_all()
    assert db_session.get(QuoteVersion, version_id).status == "EXPIRED"
    request_row = db_session.get(BulkOrderRequest, request["id"])
    assert request_row.status != "CUSTOMER_ACCEPTED"


def test_concurrency_45_accepting_an_already_accepted_quote_is_safe(
    client: TestClient, db_session: Session
) -> None:
    """(F) A customer racing to accept a quote that a prior request
    already accepted must get safe, non-corrupting behavior - here that
    is idempotent success, since accept_quote finds no SENT version left
    (it's already ACCEPTED) and the request is already CUSTOMER_ACCEPTED."""
    _user, headers, _p, variant, address, _s, _lot = _ready_bulk_customer(
        db_session, "C45", stock=Decimal("500")
    )
    request = _create_request(client, headers, address, variant)
    _admin, admin_headers = _staff(db_session, ADMIN, "C45")
    item_id = request["items"][0]["id"]
    _draft_and_send(client, admin_headers, request["id"], item_id, variant.id)

    first = client.post(f"/api/v1/bulk-orders/requests/{request['id']}/accept", headers=headers)
    assert first.status_code == 200

    second = client.post(f"/api/v1/bulk-orders/requests/{request['id']}/accept", headers=headers)
    assert second.status_code == 409  # controlled conflict - never a 500, never a new version

    db_session.expire_all()
    request_row = db_session.get(BulkOrderRequest, request["id"])
    assert request_row.status == "CUSTOMER_ACCEPTED"
    quote = db_session.query(Quote).filter_by(request_id=request["id"]).one()
    accepted_count = (
        db_session.query(QuoteVersion).filter_by(quote_id=quote.id, status="ACCEPTED").count()
    )
    assert accepted_count == 1
