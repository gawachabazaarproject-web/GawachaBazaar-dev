"""Validation of the product + inventory workflows as staff actually use them:
role boundaries called straight at the API, what deleting a size may destroy,
Undo when the stock has moved on, expiry wording inputs, error messages that
say what happened, and two people acting on the same stock at once.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.business_time import business_today
from app.core.config import settings
from app.core.roles import ADMIN, CATALOG_STAFF, HUB_STAFF, OPERATIONS
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.category import Category
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.price import Price
from app.models.product_variant import ProductVariant
from app.models.stock_movement import StockMovement
from tests.firebase_fake import auth_headers_for
from tests.test_phase_9_rbac import _create_user_with_roles

INV = "/api/v1/inventory"
CAT = "/api/v1/catalog"


def _user(db: Session, role: str, email: str):
    user = _create_user_with_roles(db, role, email=email)
    return user, auth_headers_for(db, user)


def _warehouse(db: Session, code: str) -> InventoryLocation:
    loc = InventoryLocation(
        name=f"Warehouse {code}", code=code, type="WAREHOUSE", address_line_1="1 Main St",
        city="Nagpur", state="MH", postal_code="440001", status="ACTIVE",
    )
    db.add(loc)
    db.commit()
    return loc


def _quick(client, headers, category_id, name="Tomato", **extra):
    body = {
        "category_id": category_id,
        "name": name,
        "status": "ACTIVE",
        "sizes": [
            {"quantity": "250", "unit": "G", "price": "20"},
            {"quantity": "500", "unit": "G", "price": "35"},
            {"quantity": "1", "unit": "KG", "price": "60"},
        ],
        **extra,
    }
    response = client.post(f"{CAT}/products/quick-create", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _setup(db: Session):
    category = Category(name="Vegetables", slug="vegetables", status="ACTIVE")
    db.add(category)
    db.commit()
    _, admin = _user(db, ADMIN, "admin@example.com")
    return category, admin


def _kg(db: Session, product_id: int) -> Decimal:
    db.expire_all()
    total = Decimal("0")
    for lot, variant in (
        db.query(InventoryLot, ProductVariant)
        .join(ProductVariant, ProductVariant.id == InventoryLot.variant_id)
        .filter(ProductVariant.product_id == product_id)
    ):
        total += lot.quantity * variant.quantity * (1 if variant.unit == "KG" else Decimal("0.001"))
    return total


# --------------------------------------------------------------------------
# Roles, called straight at the API
# --------------------------------------------------------------------------


def test_each_role_can_do_its_own_job_and_nothing_else(client, db_session) -> None:
    category, admin = _setup(db_session)
    main = _warehouse(db_session, "MAIN")
    product = _quick(client, admin, category.id, stock={"location_id": main.id, "amount": "20", "amount_unit": "KG"})
    pid, variant_id = product["id"], product["variants"][0]["id"]
    _, catalog = _user(db_session, CATALOG_STAFF, "catalog@example.com")
    _, hub = _user(db_session, HUB_STAFF, "hub@example.com")
    _, ops = _user(db_session, OPERATIONS, "ops@example.com")

    # Catalogue staff: product work yes, stock / delete / category structure no.
    assert client.patch(f"{CAT}/products/{pid}", json={"status": "INACTIVE"}, headers=catalog).status_code == 200
    assert client.patch(f"{CAT}/products/{pid}", json={"status": "ACTIVE"}, headers=catalog).status_code == 200
    assert client.post(f"{CAT}/variants/{variant_id}/prices", json={"price": "22"}, headers=catalog).status_code == 201
    assert client.get(f"{CAT}/products/admin/{pid}", headers=catalog).json()["stock"] is not None  # sees the numbers
    for call in (
        lambda: client.delete(f"{CAT}/products/{pid}", headers=catalog),
        lambda: client.delete(f"{CAT}/variants/{variant_id}", headers=catalog),
        lambda: client.post(f"{INV}/admin/receive", json={}, headers=catalog),
        lambda: client.get(f"{INV}/admin/products", headers=catalog),
        lambda: client.get(f"{INV}/admin/products/{pid}", headers=catalog),
        lambda: client.post(f"{INV}/admin/stock-actions/1/undo", headers=catalog),
        lambda: client.post(f"{CAT}/categories", json={"name": "X", "slug": "x"}, headers=catalog),
    ):
        assert call().status_code == 403

    # Warehouse staff: stock yes, catalogue / prices no.
    for headers in (hub, ops):
        assert client.get(f"{INV}/admin/products/{pid}", headers=headers).status_code == 200
        assert client.post(
            f"{INV}/admin/products/{pid}/remove", json={"amount": "1", "amount_unit": "KG", "reason": "Damaged"}, headers=headers
        ).status_code == 200
        for call in (
            lambda h=headers: client.post(f"{CAT}/products/quick-create", json={}, headers=h),
            lambda h=headers: client.patch(f"{CAT}/products/{pid}", json={"status": "INACTIVE"}, headers=h),
            lambda h=headers: client.post(f"{CAT}/variants/{variant_id}/prices", json={"price": "1"}, headers=h),
            lambda h=headers: client.delete(f"{CAT}/products/{pid}", headers=h),
            lambda h=headers: client.delete(f"{CAT}/variants/{variant_id}", headers=h),
        ):
            assert call().status_code == 403


# --------------------------------------------------------------------------
# Deleting a size must never destroy history
# --------------------------------------------------------------------------


def test_a_size_with_any_history_is_hidden_not_deleted(client, db_session) -> None:
    category, admin = _setup(db_session)
    main = _warehouse(db_session, "MAIN")
    product = _quick(client, admin, category.id, stock={"location_id": main.id, "amount": "5", "amount_unit": "KG"})
    first, second, third = (v["id"] for v in product["variants"])
    delete = lambda vid: client.delete(f"{CAT}/variants/{vid}", headers=admin)  # noqa: E731

    assert delete(first).status_code == 409  # it holds the opening stock
    assert db_session.query(ProductVariant).count() == 3

    # A customer has the 500 g size in a cart.
    customer = _create_user_with_roles(db_session, "CUSTOMER", email="shopper@example.com")
    cart = Cart(user_id=customer.id, status="ACTIVE")
    db_session.add(cart)
    db_session.commit()
    db_session.add(CartItem(cart_id=cart.id, variant_id=second, quantity=Decimal("1")))
    db_session.commit()
    refused = delete(second)
    assert refused.status_code == 409 and "cart" in refused.json()["message"].lower()
    assert db_session.query(CartItem).count() == 1  # nobody's cart was emptied

    # The 1 kg price was changed: history is kept.
    client.post(f"{CAT}/variants/{third}/prices", json={"price": "65"}, headers=admin)
    changed = delete(third)
    assert changed.status_code == 409 and "history" in changed.json()["message"].lower()
    assert db_session.query(Price).filter(Price.variant_id == third).count() == 2

    # A mistaken, just-added size (one price, no stock, not in a cart) can still go.
    extra = client.post(
        f"{CAT}/products/{product['id']}/variants",
        json={"name": "2 kg", "sku": "TOMATO-2KG", "unit": "KG", "quantity": "2"},
        headers=admin,
    ).json()
    client.post(f"{CAT}/variants/{extra['id']}/prices", json={"price": "100"}, headers=admin)
    assert delete(extra["id"]).status_code == 204
    assert db_session.query(ProductVariant).filter(ProductVariant.id == extra["id"]).count() == 0


def test_the_only_size_of_a_live_product_cannot_be_deleted(client, db_session) -> None:
    category, admin = _setup(db_session)
    product = client.post(
        f"{CAT}/products/quick-create",
        json={"category_id": category.id, "name": "Onion", "status": "ACTIVE", "sizes": [{"quantity": "1", "unit": "KG", "price": "30"}]},
        headers=admin,
    ).json()
    response = client.delete(f"{CAT}/variants/{product['variants'][0]['id']}", headers=admin)
    assert response.status_code == 409 and "only size" in response.json()["message"].lower()


# --------------------------------------------------------------------------
# Undo when the stock has moved on
# --------------------------------------------------------------------------


def _receive(client, headers, variant_id, location_id, amount, **extra):
    r = client.post(
        f"{INV}/admin/receive",
        json={"variant_id": variant_id, "location_id": location_id, "amount": str(amount), "amount_unit": "KG", **extra},
        headers=headers,
    )
    assert r.status_code == 200, r.text


def test_undo_is_refused_when_the_added_stock_has_since_been_taken(client, db_session) -> None:
    category, admin = _setup(db_session)
    main = _warehouse(db_session, "MAIN")
    product = _quick(client, admin, category.id)
    kg_size = product["variants"][2]["id"]
    _receive(client, admin, kg_size, main.id, 10)
    up = client.post(f"{INV}/admin/products/{product['id']}/correct", json={"physical_amount": "15", "amount_unit": "KG"}, headers=admin).json()
    # Someone then removes nearly everything, so the 5 kg surplus is no longer there to take back.
    client.post(f"{INV}/admin/products/{product['id']}/remove", json={"amount": "13", "amount_unit": "KG", "reason": "Waste"}, headers=admin)
    refused = client.post(f"{INV}/admin/stock-actions/{up['operation_id']}/undo", headers=admin)
    assert refused.status_code == 409
    assert _kg(db_session, product["id"]) == Decimal("2")  # untouched by the failed undo
    assert db_session.query(StockMovement).filter(StockMovement.reference_type == "product_undo").count() == 0


def test_undo_never_breaks_reserved_stock_and_keeps_the_history(client, db_session) -> None:
    category, admin = _setup(db_session)
    main = _warehouse(db_session, "MAIN")
    product = _quick(client, admin, category.id)
    _receive(client, admin, product["variants"][2]["id"], main.id, 10)
    removed = client.post(f"{INV}/admin/products/{product['id']}/remove", json={"amount": "2", "amount_unit": "KG", "reason": "Damaged"}, headers=admin).json()
    lot = db_session.query(InventoryLot).one()
    lot.reserved_quantity = Decimal("8")  # an order now holds all that is left
    db_session.commit()
    before = db_session.query(StockMovement).count()

    undone = client.post(f"{INV}/admin/stock-actions/{removed['operation_id']}/undo", headers=admin)
    assert undone.status_code == 200  # putting stock back is always safe
    db_session.expire_all()
    lot = db_session.query(InventoryLot).one()
    assert lot.quantity == Decimal("10") and lot.reserved_quantity == Decimal("8")
    assert lot.reserved_quantity <= lot.quantity
    assert db_session.query(StockMovement).count() == before + 1  # nothing rewritten, one entry added


# --------------------------------------------------------------------------
# Opening stock vs receiving afterwards: same result, nothing doubled
# --------------------------------------------------------------------------


def test_opening_stock_and_receive_later_end_in_the_same_stock(client, db_session) -> None:
    category, admin = _setup(db_session)
    main = _warehouse(db_session, "MAIN")
    with_opening = _quick(client, admin, category.id, name="Tomato", stock={"location_id": main.id, "amount": "50", "amount_unit": "KG"})
    without = _quick(client, admin, category.id, name="Potato")
    assert _kg(db_session, without["id"]) == Decimal("0")
    _receive(client, admin, without["variants"][0]["id"], main.id, 50)

    def total(pid):
        return Decimal(client.get(f"{INV}/admin/products/{pid}", headers=admin).json()["totals"][0]["amount"])

    assert total(with_opening["id"]) == total(without["id"]) == Decimal("50")
    assert _kg(db_session, with_opening["id"]) == Decimal("50")  # once, not twice
    receipts = db_session.query(StockMovement).filter(StockMovement.movement_type == "RECEIPT").count()
    assert receipts == 2


# --------------------------------------------------------------------------
# Expiry wording inputs
# --------------------------------------------------------------------------


def test_expiry_days_left_covers_today_tomorrow_expired_and_the_soonest_wins(client, db_session) -> None:
    category, admin = _setup(db_session)
    main = _warehouse(db_session, "MAIN")
    today = business_today()
    product = _quick(client, admin, category.id)
    kg_size = product["variants"][2]["id"]
    card = lambda: client.get(f"{INV}/admin/products/{product['id']}", headers=admin).json()  # noqa: E731

    _receive(client, admin, kg_size, main.id, 10)
    assert card()["expiry"] is None  # no expiry

    _receive(client, admin, kg_size, main.id, 4, expiry_date=(today + timedelta(days=3)).isoformat())
    assert card()["expiry"]["days_left"] == 3
    _receive(client, admin, kg_size, main.id, 2, expiry_date=(today + timedelta(days=1)).isoformat())
    assert card()["expiry"]["days_left"] == 1 and Decimal(card()["expiry"]["amount"]) == Decimal("2")
    _receive(client, admin, kg_size, main.id, 1, expiry_date=today.isoformat())
    assert card()["expiry"]["days_left"] == 0

    # A lot that is already past its date (as time goes by) outranks the valid ones.
    from app.models.batch import Batch

    soon = db_session.query(Batch).filter(Batch.expiry_date == today).one()
    soon.harvest_date = today - timedelta(days=5)
    soon.expiry_date = today - timedelta(days=1)
    db_session.commit()
    expired = card()["expiry"]
    assert expired["days_left"] == -1 and Decimal(expired["amount"]) == Decimal("1")
    summary = client.get(f"{INV}/admin/products/summary", headers=admin).json()
    assert summary["expiring"] == 1
    listing = client.get(f"{INV}/admin/products", params={"status": "expiring"}, headers=admin).json()["items"]
    assert [i["product_id"] for i in listing] == [product["id"]]


def test_expiry_input_is_validated(client, db_session) -> None:
    category, admin = _setup(db_session)
    main = _warehouse(db_session, "MAIN")
    product = _quick(client, admin, category.id)
    base = {"variant_id": product["variants"][2]["id"], "location_id": main.id, "amount": "5", "amount_unit": "KG"}
    for bad in ("2026-13-45", "tomorrow", "", "31/12/2030", (business_today() - timedelta(days=1)).isoformat()):
        assert client.post(f"{INV}/admin/receive", json={**base, "expiry_date": bad}, headers=admin).status_code == 422, bad
    assert client.post(f"{INV}/admin/receive", json={**base, "expiry_date": business_today().isoformat()}, headers=admin).status_code == 200


def test_today_follows_the_shops_timezone_not_the_servers() -> None:
    original = settings.BAZAAR_TIMEZONE
    try:
        settings.BAZAAR_TIMEZONE = "Pacific/Kiritimati"  # UTC+14
        east = business_today()
        settings.BAZAAR_TIMEZONE = "Pacific/Pago_Pago"  # UTC-11
        west = business_today()
    finally:
        settings.BAZAAR_TIMEZONE = original
    assert east - west >= timedelta(days=1)  # 25 hours apart: never the same calendar day
    assert isinstance(east, date)


# --------------------------------------------------------------------------
# Error messages say what happened and whether stock changed
# --------------------------------------------------------------------------


def test_errors_explain_themselves_and_leave_stock_alone(client, db_session) -> None:
    category, admin = _setup(db_session)
    main = _warehouse(db_session, "MAIN")
    other = _warehouse(db_session, "OTHER")
    product = _quick(client, admin, category.id, stock={"location_id": main.id, "amount": "12", "amount_unit": "KG"})
    pid = product["id"]

    too_much = client.post(f"{INV}/admin/products/{pid}/remove", json={"amount": "20", "amount_unit": "KG", "reason": "Damaged"}, headers=admin)
    assert too_much.status_code == 422
    assert "12 kg" in too_much.json()["message"] and "available" in too_much.json()["message"]

    for bad in ("0", "-3", "abc"):
        r = client.post(f"{INV}/admin/products/{pid}/remove", json={"amount": bad, "amount_unit": "KG", "reason": "Damaged"}, headers=admin)
        assert r.status_code == 422
    assert client.post(f"{INV}/admin/products/{pid}/remove", json={"amount": "1", "amount_unit": "KG", "reason": ""}, headers=admin).status_code == 422
    assert client.post(
        f"{INV}/admin/products/{pid}/move",
        json={"amount": "1", "amount_unit": "KG", "from_location_id": main.id, "to_location_id": main.id},
        headers=admin,
    ).status_code == 422
    assert client.post(
        f"{INV}/admin/products/{pid}/move",
        json={"amount": "50", "amount_unit": "KG", "from_location_id": main.id, "to_location_id": other.id},
        headers=admin,
    ).status_code == 422
    assert client.post(f"{INV}/admin/products/999999/correct", json={"physical_amount": "1", "amount_unit": "KG"}, headers=admin).status_code == 404
    assert _kg(db_session, pid) == Decimal("12")
    assert db_session.query(StockMovement).count() == 1  # only the opening receipt


# --------------------------------------------------------------------------
# Two people at once
# --------------------------------------------------------------------------


def test_two_removals_at_once_never_take_more_than_there_is(client, db_session) -> None:
    category, admin = _setup(db_session)
    main = _warehouse(db_session, "MAIN")
    product = _quick(client, admin, category.id, stock={"location_id": main.id, "amount": "10", "amount_unit": "KG"})
    body = {"amount": "6", "amount_unit": "KG", "reason": "Damaged"}

    def remove():
        return client.post(f"{INV}/admin/products/{product['id']}/remove", json=body, headers=admin).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(f.result() for f in [pool.submit(remove), pool.submit(remove)])
    assert codes == [200, 422]  # one wins, the other is told there is not enough left
    assert _kg(db_session, product["id"]) == Decimal("4")
    lot = db_session.query(InventoryLot).one()
    assert lot.quantity >= lot.reserved_quantity >= 0


# --------------------------------------------------------------------------
# One definition of "needs attention" for stock
# --------------------------------------------------------------------------


def test_header_alert_inventory_chips_and_products_list_agree(client, db_session) -> None:
    category, admin = _setup(db_session)
    main = _warehouse(db_session, "MAIN")
    # Three sizes all running low: still ONE product that needs restocking.
    low = _quick(client, admin, category.id, name="Tomato", stock={"location_id": main.id, "amount": "3", "amount_unit": "KG"})
    out = _quick(client, admin, category.id, name="Onion")  # live, never stocked
    healthy = _quick(client, admin, category.id, name="Potato", stock={"location_id": main.id, "amount": "100", "amount_unit": "KG"})
    # A draft with no stock cannot be bought, so it is not an alarm.
    draft = client.post(
        f"{CAT}/products/quick-create",
        json={"category_id": category.id, "name": "Mango", "status": "DRAFT", "sizes": [{"quantity": "1", "unit": "KG", "price": "90"}]},
        headers=admin,
    ).json()

    alerts = client.get(f"{INV}/admin/stock-alerts", headers=admin).json()
    summary = client.get(f"{INV}/admin/products/summary", headers=admin).json()
    assert (alerts["products_out"], alerts["products_low"]) == (1, 1)
    assert (summary["out"], summary["low"]) == (alerts["products_out"], alerts["products_low"])
    assert alerts["count"] > alerts["products_low"] + alerts["products_out"]  # per size is a bigger number

    def names(status):
        return [i["product_name"] for i in client.get(f"{INV}/admin/products", params={"status": status}, headers=admin).json()["items"]]

    assert names("low") == ["Tomato"] and names("out") == ["Onion"]
    listing = {i["name"]: i for i in client.get(f"{CAT}/products/admin", headers=admin).json()["items"]}
    assert listing["Tomato"]["stock_status"] == "LOW" and listing["Tomato"]["stock_text"] == "3 kg"
    assert listing["Onion"]["stock_status"] == "OUT"
    assert listing["Potato"]["stock_status"] == "OK" and listing["Potato"]["stock_text"] == "100 kg"
    assert listing["Mango"]["status"] == "DRAFT" and healthy["id"] and low["id"] and out["id"] and draft["id"]


def test_low_stock_levels_need_stock_rights_not_just_product_rights(client, db_session) -> None:
    category, admin = _setup(db_session)
    product = _quick(client, admin, category.id)
    vid = product["variants"][0]["id"]
    _, catalog = _user(db_session, CATALOG_STAFF, "catalog@example.com")
    assert client.patch(f"{CAT}/variants/{vid}", json={"reserve_level": "5"}, headers=catalog).status_code == 403
    assert client.patch(f"{CAT}/variants/{vid}", json={"name": "250 g pack"}, headers=catalog).status_code == 200
    assert client.patch(f"{CAT}/variants/{vid}", json={"reserve_level": "5"}, headers=admin).status_code == 200
    assert db_session.get(ProductVariant, vid).reserve_level == Decimal("5")


# --------------------------------------------------------------------------
# Final pre-client hardening
# --------------------------------------------------------------------------


def test_opening_stock_then_receiving_more_adds_up_without_double_counting(client, db_session) -> None:
    category, admin = _setup(db_session)
    main = _warehouse(db_session, "MAIN")
    product = _quick(client, admin, category.id, stock={"location_id": main.id, "amount": "50", "amount_unit": "KG"})
    card = lambda: client.get(f"{INV}/admin/products/{product['id']}", headers=admin).json()  # noqa: E731
    assert Decimal(card()["totals"][0]["amount"]) == Decimal("50")  # A: only the opening stock
    _receive(client, admin, product["variants"][2]["id"], main.id, 30)
    assert Decimal(card()["totals"][0]["amount"]) == Decimal("80")  # C: opening + received
    assert db_session.query(StockMovement).filter(StockMovement.movement_type == "RECEIPT").count() == 2


def test_the_products_list_stock_is_available_kg_across_sizes_lots_warehouses_and_reservations(client, db_session) -> None:
    category, admin = _setup(db_session)
    main = _warehouse(db_session, "MAIN")
    other = _warehouse(db_session, "OTHER")
    product = _quick(client, admin, category.id)
    small, _, kg_size = (v["id"] for v in product["variants"])
    _receive(client, admin, kg_size, main.id, 10)  # 10 kg in 1 kg packs
    _receive(client, admin, small, other.id, 4)  # 4 kg arriving as 250 g packs, another warehouse
    lot = db_session.query(InventoryLot).filter(InventoryLot.variant_id == kg_size).one()
    lot.reserved_quantity = Decimal("3")  # 3 kg promised to orders
    db_session.commit()

    row = next(i for i in client.get(f"{CAT}/products/admin", headers=admin).json()["items"] if i["id"] == product["id"])
    card = client.get(f"{INV}/admin/products/{product['id']}", headers=admin).json()
    assert row["stock_text"] == "11 kg"  # (10 + 4) physically, minus the 3 reserved
    total = card["totals"][0]
    assert (Decimal(total["amount"]), Decimal(total["reserved_amount"]), Decimal(total["on_hand_amount"])) == (
        Decimal("11"), Decimal("3"), Decimal("14"),
    )
    assert {w["location_name"]: Decimal(w["amount"]) for w in card["warehouses"]} == {main.name: Decimal("7"), other.name: Decimal("4")}


def test_hidden_and_draft_products_never_raise_a_stock_alarm(client, db_session) -> None:
    category, admin = _setup(db_session)
    live = _quick(client, admin, category.id, name="Tomato")  # live, no stock -> OUT
    hidden = _quick(client, admin, category.id, name="Onion")
    client.patch(f"{CAT}/products/{hidden['id']}", json={"status": "INACTIVE"}, headers=admin)
    summary = client.get(f"{INV}/admin/products/summary", headers=admin).json()
    alerts = client.get(f"{INV}/admin/stock-alerts", headers=admin).json()
    assert (summary["out"], alerts["products_out"]) == (1, 1)
    chips = client.get(f"{INV}/admin/products", params={"status": "out"}, headers=admin).json()["items"]
    assert [c["product_name"] for c in chips] == ["Tomato"] and live["id"]


def test_warehouse_staff_may_work_on_every_warehouse_today(client, db_session) -> None:
    """Documents the CURRENT rule (no user-to-warehouse link exists): inventory
    permissions are not scoped to a warehouse. If the business decides otherwise
    this test is the one to change."""
    category, admin = _setup(db_session)
    a, b = _warehouse(db_session, "A"), _warehouse(db_session, "B")
    product = _quick(client, admin, category.id, stock={"location_id": a.id, "amount": "20", "amount_unit": "KG"})
    _, hub = _user(db_session, HUB_STAFF, "hub@example.com")
    moved = client.post(
        f"{INV}/admin/products/{product['id']}/move",
        json={"amount": "5", "amount_unit": "KG", "from_location_id": a.id, "to_location_id": b.id},
        headers=hub,
    )
    assert moved.status_code == 200
    assert client.post(
        f"{INV}/admin/products/{product['id']}/remove",
        json={"amount": "1", "amount_unit": "KG", "reason": "Damaged", "location_id": b.id},
        headers=hub,
    ).status_code == 200
