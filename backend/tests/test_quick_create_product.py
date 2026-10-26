"""Quick create: a whole product (sizes, prices, photo, opening stock) in one
transaction, and the CATALOG_STAFF role that uses it.

The point of the endpoint is atomicity: the old Admin flow made ~11 separate
requests and could leave a half-built draft. Every failure test below checks
that NOTHING was saved.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.roles import ADMIN, CATALOG_STAFF, CUSTOMER, HUB_STAFF
from app.models.admin_action_log import AdminActionLog
from app.models.batch import Batch
from app.models.category import Category
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.price import Price
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.product_variant import ProductVariant
from app.models.stock_movement import StockMovement
from tests.firebase_fake import auth_headers_for
from tests.test_phase_9_rbac import _create_user_with_roles

URL = "/api/v1/catalog/products/quick-create"


def _user(db: Session, role: str, email: str):
    user = _create_user_with_roles(db, role, email=email)
    return user, auth_headers_for(db, user)


def _category(db: Session) -> Category:
    category = Category(name="Vegetables", slug="vegetables", status="ACTIVE")
    db.add(category)
    db.commit()
    return category


def _warehouse(db: Session) -> InventoryLocation:
    loc = InventoryLocation(
        name="Main Warehouse", code="MAIN", type="WAREHOUSE", address_line_1="1 Main St",
        city="Nagpur", state="MH", postal_code="440001", status="ACTIVE",
    )
    db.add(loc)
    db.commit()
    return loc


def _payload(category_id: int, **overrides) -> dict:
    body = {
        "category_id": category_id,
        "name": "Tomato",
        "sizes": [
            {"quantity": "250", "unit": "G", "price": "20"},
            {"quantity": "500", "unit": "G", "price": "35"},
            {"quantity": "1", "unit": "KG", "price": "60"},
        ],
    }
    body.update(overrides)
    return body


def _counts(db: Session) -> tuple[int, int, int, int, int]:
    db.expire_all()
    return (
        db.query(Product).count(),
        db.query(ProductVariant).count(),
        db.query(Price).count(),
        db.query(InventoryLot).count(),
        db.query(Batch).count(),
    )


def test_creates_the_whole_product_in_one_request(client, db_session) -> None:
    admin, headers = _user(db_session, ADMIN, "admin@example.com")
    category = _category(db_session)
    warehouse = _warehouse(db_session)
    expiry = (date.today() + timedelta(days=3)).isoformat()

    response = client.post(
        URL,
        json=_payload(
            category.id,
            status="ACTIVE",
            description="Fresh",
            image_url="https://example.com/t.jpg",
            stock={"location_id": warehouse.id, "amount": "50", "amount_unit": "KG", "expiry_date": expiry},
        ),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "ACTIVE" and body["slug"] == "tomato"
    assert [v["name"] for v in body["variants"]] == ["250 g", "500 g", "1 kg"]
    assert [v["sku"] for v in body["variants"]] == ["TOMATO-250-G", "TOMATO-500-G", "TOMATO-1-KG"]
    assert [Decimal(v["current_price"]["price"]) for v in body["variants"]] == [Decimal("20"), Decimal("35"), Decimal("60")]
    assert body["images"][0]["is_primary"] is True

    assert _counts(db_session) == (1, 3, 3, 1, 1)
    lot = db_session.query(InventoryLot).one()
    # 50 kg went in against the first size (250 g): 200 packs, one receipt.
    assert lot.quantity == Decimal("200") and lot.location_id == warehouse.id
    assert db_session.query(StockMovement).one().movement_type == "RECEIPT"
    assert db_session.query(Batch).one().expiry_date.isoformat() == expiry
    assert db_session.query(ProductImage).count() == 1
    actions = {a.action for a in db_session.query(AdminActionLog)}
    assert {"product.create", "product.variant.create", "product.price.create"} <= actions


def test_a_draft_without_stock_or_photo_is_valid(client, db_session) -> None:
    _, headers = _user(db_session, ADMIN, "admin@example.com")
    category = _category(db_session)
    response = client.post(URL, json=_payload(category.id), headers=headers)
    assert response.status_code == 201
    assert response.json()["status"] == "DRAFT"
    assert _counts(db_session) == (1, 3, 3, 0, 0)


def test_repeating_a_name_gets_a_unique_web_address_and_codes(client, db_session) -> None:
    _, headers = _user(db_session, ADMIN, "admin@example.com")
    category = _category(db_session)
    first = client.post(URL, json=_payload(category.id), headers=headers).json()
    second = client.post(URL, json=_payload(category.id), headers=headers)
    assert second.status_code == 201
    second = second.json()
    assert (first["slug"], second["slug"]) == ("tomato", "tomato-2")
    skus = [v["sku"] for v in first["variants"]] + [v["sku"] for v in second["variants"]]
    assert len(set(skus)) == 6


def test_a_marathi_name_still_gets_a_web_address(client, db_session) -> None:
    _, headers = _user(db_session, ADMIN, "admin@example.com")
    category = _category(db_session)
    response = client.post(URL, json=_payload(category.id, name="टोमॅटो"), headers=headers)
    assert response.status_code == 201
    assert response.json()["slug"].startswith("product-")
    assert response.json()["name"] == "टोमॅटो"


def test_a_failing_stock_step_saves_nothing(client, db_session) -> None:
    _, headers = _user(db_session, ADMIN, "admin@example.com")
    category = _category(db_session)
    response = client.post(
        URL,
        json=_payload(category.id, stock={"location_id": 999999, "amount": "50", "amount_unit": "KG"}),
        headers=headers,
    )
    assert response.status_code == 404
    assert _counts(db_session) == (0, 0, 0, 0, 0)
    assert db_session.query(AdminActionLog).count() == 0  # audit rows roll back too


def test_stock_in_a_unit_no_size_uses_saves_nothing(client, db_session) -> None:
    _, headers = _user(db_session, ADMIN, "admin@example.com")
    category = _category(db_session)
    warehouse = _warehouse(db_session)
    response = client.post(
        URL,
        json=_payload(category.id, stock={"location_id": warehouse.id, "amount": "5", "amount_unit": "L"}),
        headers=headers,
    )
    assert response.status_code == 422
    assert _counts(db_session) == (0, 0, 0, 0, 0)


def test_invalid_input_is_rejected_before_anything_is_saved(client, db_session) -> None:
    _, headers = _user(db_session, ADMIN, "admin@example.com")
    category = _category(db_session)
    bad_price = _payload(category.id, sizes=[{"quantity": "1", "unit": "KG", "price": "0"}])
    no_sizes = _payload(category.id, sizes=[])
    twice = _payload(category.id, sizes=[
        {"quantity": "1", "unit": "KG", "price": "60"}, {"quantity": "1.000", "unit": "KG", "price": "55"},
    ])
    bad_unit = _payload(category.id, sizes=[{"quantity": "1", "unit": "BAG", "price": "60"}])
    for body in (bad_price, no_sizes, twice, bad_unit):
        assert client.post(URL, json=body, headers=headers).status_code == 422
    assert client.post(URL, json=_payload(999999), headers=headers).status_code == 404
    assert _counts(db_session) == (0, 0, 0, 0, 0)


def test_catalogue_staff_can_create_products_but_not_stock_or_delete(client, db_session) -> None:
    _, headers = _user(db_session, CATALOG_STAFF, "catalog@example.com")
    category = _category(db_session)
    warehouse = _warehouse(db_session)

    ok = client.post(URL, json=_payload(category.id, image_url="https://example.com/t.jpg"), headers=headers)
    assert ok.status_code == 201, ok.text
    product_id = ok.json()["id"]

    stock = client.post(
        URL,
        json=_payload(category.id, name="Potato", stock={"location_id": warehouse.id, "amount": "5", "amount_unit": "KG"}),
        headers=headers,
    )
    assert stock.status_code == 403
    assert _counts(db_session) == (1, 3, 3, 0, 0)  # the refused request left nothing behind

    assert client.delete(f"/api/v1/catalog/products/{product_id}", headers=headers).status_code == 403
    assert client.post("/api/v1/catalog/categories", json={"name": "X", "slug": "x"}, headers=headers).status_code == 403
    # They can change prices and edit the product.
    variant_id = ok.json()["variants"][0]["id"]
    price = client.post(f"/api/v1/catalog/variants/{variant_id}/prices", json={"price": "25"}, headers=headers)
    assert price.status_code == 201
    assert client.patch(f"/api/v1/catalog/products/{product_id}", json={"status": "ACTIVE"}, headers=headers).status_code == 200
    # Stock stays out of reach.
    assert client.get("/api/v1/inventory/admin/products", headers=headers).status_code == 403
    assert client.post("/api/v1/inventory/admin/receive", json={}, headers=headers).status_code == 403


def test_other_roles_cannot_quick_create(client, db_session) -> None:
    category = _category(db_session)
    for role in (HUB_STAFF, CUSTOMER):
        _, headers = _user(db_session, role, f"{role.lower()}@example.com")
        assert client.post(URL, json=_payload(category.id), headers=headers).status_code == 403
    assert client.post(URL, json=_payload(category.id)).status_code == 401
    assert _counts(db_session) == (0, 0, 0, 0, 0)


def test_admin_views_show_what_is_missing_and_the_stock_in_kg(client, db_session) -> None:
    _, headers = _user(db_session, ADMIN, "admin@example.com")
    category = _category(db_session)
    warehouse = _warehouse(db_session)
    created = client.post(
        URL,
        json=_payload(category.id, stock={"location_id": warehouse.id, "amount": "50", "amount_unit": "KG"}),
        headers=headers,
    ).json()
    # A size added later without a price shows up as "not priced".
    client.post(
        f"/api/v1/catalog/products/{created['id']}/variants",
        json={"name": "2 kg", "sku": "TOMATO-2KG", "unit": "KG", "quantity": "2"},
        headers=headers,
    )

    listing = client.get("/api/v1/catalog/products/admin", headers=headers).json()["items"][0]
    assert (listing["active_variant_count"], listing["priced_variant_count"]) == (4, 3)

    detail = client.get(f"/api/v1/catalog/products/admin/{created['id']}", headers=headers).json()
    total = detail["stock"]["totals"][0]
    assert (Decimal(total["amount"]), total["amount_unit"]) == (Decimal("50"), "kg")
    assert detail["stock"]["warehouses"][0]["location_name"] == "Main Warehouse"


def test_catalogue_staff_do_not_receive_customers_order_events() -> None:
    from app.api.v1.realtime import receives_order_events
    from app.core.roles import DELIVERY_PARTNER, OPERATIONS, SUPPORT

    assert receives_order_events([ADMIN]) and receives_order_events([OPERATIONS]) and receives_order_events([SUPPORT])
    assert not receives_order_events([CATALOG_STAFF])
    assert not receives_order_events([DELIVERY_PARTNER])
    assert not receives_order_events([CUSTOMER])
    assert receives_order_events([CATALOG_STAFF, HUB_STAFF])


def test_a_product_cannot_go_live_without_a_size_and_a_price_on_every_size(client, db_session) -> None:
    _, headers = _user(db_session, ADMIN, "admin@example.com")
    category = _category(db_session)
    product = client.post(
        "/api/v1/catalog/products",
        json={"category_id": category.id, "name": "Onion", "slug": "onion", "status": "DRAFT"},
        headers=headers,
    ).json()
    publish = lambda: client.patch(f"/api/v1/catalog/products/{product['id']}", json={"status": "ACTIVE"}, headers=headers)  # noqa: E731

    no_size = publish()
    assert no_size.status_code == 422 and "size" in no_size.json()["message"].lower()

    variant = client.post(
        f"/api/v1/catalog/products/{product['id']}/variants",
        json={"name": "1 kg", "sku": "ONION-1KG", "unit": "KG", "quantity": "1"},
        headers=headers,
    ).json()
    no_price = publish()
    assert no_price.status_code == 422 and "1 kg" in no_price.json()["message"]
    assert db_session.get(Product, product["id"]).status == "DRAFT"

    client.post(f"/api/v1/catalog/variants/{variant['id']}/prices", json={"price": "30"}, headers=headers)
    assert publish().status_code == 200
    db_session.expire_all()
    assert db_session.get(Product, product["id"]).status == "ACTIVE"
    # Editing a live product (not a publish) is never blocked by this rule.
    assert client.patch(f"/api/v1/catalog/products/{product['id']}", json={"name": "Red Onion"}, headers=headers).status_code == 200
