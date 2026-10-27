"""Product-level stock actions (correct / remove / move / undo), receive with
expiry, and the stock summary behind the Inventory page.

These are the operations staff think in ("I counted 43 kg"); the server picks
the lots. Every test re-reads the database after the call, because the risk in
this area is an API that says "done" while a write was rolled back, or the
reverse: a failure that still changed stock.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.core.business_time import business_today
from app.core.roles import ADMIN, CATALOG_STAFF, CUSTOMER, HUB_STAFF, OPERATIONS
from app.models.admin_action_log import AdminActionLog
from app.models.batch import Batch
from app.models.category import Category
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.stock_movement import StockMovement
from app.services.inventory import InventoryService
from tests.firebase_fake import auth_headers_for
from tests.test_phase_9_rbac import _create_user_with_roles

BASE = "/api/v1/inventory"


def _user(db: Session, role: str, email: str):
    user = _create_user_with_roles(db, role, email=email)
    return user, auth_headers_for(db, user)


def _location(db: Session, code: str, status: str = "ACTIVE") -> InventoryLocation:
    loc = InventoryLocation(
        name=f"Warehouse {code}", code=code, type="WAREHOUSE", address_line_1="1 Main St",
        city="Nagpur", state="MH", postal_code="440001", status=status,
    )
    db.add(loc)
    db.commit()
    return loc


def _tomato(db: Session) -> tuple[Product, dict[str, ProductVariant]]:
    category = Category(name="Vegetables", slug="vegetables", status="ACTIVE")
    db.add(category)
    db.commit()
    product = Product(category_id=category.id, name="Tomato", slug="tomato", status="ACTIVE")
    db.add(product)
    db.commit()
    sizes = {}
    for label, unit, qty in (("250 g", "G", "250"), ("500 g", "G", "500"), ("1 kg", "KG", "1")):
        v = ProductVariant(
            product_id=product.id, name=label, sku=f"TOMATO-{label.replace(' ', '').upper()}",
            unit=unit, quantity=Decimal(qty), status="ACTIVE",
        )
        db.add(v)
        sizes[label] = v
    db.commit()
    return product, sizes


def _receive(client, headers, variant_id, location_id, amount, unit="KG", **extra):
    response = client.post(
        f"{BASE}/admin/receive",
        json={"variant_id": variant_id, "location_id": location_id, "amount": str(amount), "amount_unit": unit, **extra},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _on_hand_kg(db: Session, product_id: int, location_id: int | None = None) -> Decimal:
    db.expire_all()
    total = Decimal("0")
    q = db.query(InventoryLot, ProductVariant).join(ProductVariant, ProductVariant.id == InventoryLot.variant_id)
    q = q.filter(ProductVariant.product_id == product_id)
    if location_id:
        q = q.filter(InventoryLot.location_id == location_id)
    for lot, variant in q.all():
        grams = variant.quantity * (1000 if variant.unit == "KG" else 1)
        total += lot.quantity * grams
    return total / 1000


def _setup(db: Session, client):
    admin, headers = _user(db, ADMIN, "admin@example.com")
    product, sizes = _tomato(db)
    main = _location(db, "MAIN")
    return admin, headers, product, sizes, main


# --------------------------------------------------------------------------
# Receive with expiry
# --------------------------------------------------------------------------


def test_receive_records_the_expiry_on_the_automatic_delivery(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    expiry = business_today() + timedelta(days=3)
    lot = _receive(client, headers, sizes["1 kg"].id, main.id, 50, expiry_date=expiry.isoformat())
    assert lot["batch_expiry_date"] == expiry.isoformat()
    batch = db_session.query(Batch).one()
    assert batch.expiry_date == expiry
    assert _on_hand_kg(db_session, product.id) == Decimal("50")


def test_receive_rejects_a_past_expiry_and_expiry_with_a_batch(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    past = (business_today() - timedelta(days=1)).isoformat()
    for body in (
        {"expiry_date": past},
        {"expiry_date": (business_today() + timedelta(days=2)).isoformat(), "batch_id": 1},
    ):
        response = client.post(
            f"{BASE}/admin/receive",
            json={"variant_id": sizes["1 kg"].id, "location_id": main.id, "amount": "5", "amount_unit": "KG", **body},
            headers=headers,
        )
        assert response.status_code == 422
    assert db_session.query(InventoryLot).count() == 0


def test_receive_converts_kg_into_packs_of_the_chosen_size(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    lot = _receive(client, headers, sizes["250 g"].id, main.id, 50)
    assert Decimal(lot["on_hand"]) == Decimal("200")  # 200 packs of 250 g
    assert _on_hand_kg(db_session, product.id) == Decimal("50")


# --------------------------------------------------------------------------
# Correct stock
# --------------------------------------------------------------------------


def test_correct_down_calculates_the_difference_and_records_one_audited_operation(client, db_session) -> None:
    admin, headers, product, sizes, main = _setup(db_session, client)
    _receive(client, headers, sizes["1 kg"].id, main.id, 50)

    response = client.post(
        f"{BASE}/admin/products/{product.id}/correct",
        json={"physical_amount": "43", "amount_unit": "KG", "reason": "Physical count"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(body["difference"]) == Decimal("-7")
    assert body["operation_id"] and body["undo_until"]
    assert _on_hand_kg(db_session, product.id) == Decimal("43")

    movements = db_session.query(StockMovement).filter(StockMovement.reference_type == "product_correct").all()
    assert [m.movement_type for m in movements] == ["ADJUSTMENT_OUT"]
    assert movements[0].quantity == Decimal("7")
    assert all(m.reference_id == body["operation_id"] for m in movements)
    audit = db_session.get(AdminActionLog, body["operation_id"])
    assert audit.action == "inventory.correct_product" and audit.admin_user_id == admin.id


def test_correct_up_adds_the_surplus_to_the_newest_lot(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    _receive(client, headers, sizes["1 kg"].id, main.id, 30)
    _receive(client, headers, sizes["1 kg"].id, main.id, 20)

    response = client.post(
        f"{BASE}/admin/products/{product.id}/correct",
        json={"physical_amount": "55", "amount_unit": "KG"},
        headers=headers,
    )
    assert response.status_code == 200
    assert Decimal(response.json()["difference"]) == Decimal("5")
    lots = db_session.query(InventoryLot).order_by(InventoryLot.id).all()
    assert [lot.quantity for lot in lots] == [Decimal("30"), Decimal("25")]


def test_correct_with_a_matching_count_changes_nothing(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    _receive(client, headers, sizes["1 kg"].id, main.id, 50)
    before = db_session.query(StockMovement).count()
    response = client.post(
        f"{BASE}/admin/products/{product.id}/correct",
        json={"physical_amount": "50", "amount_unit": "KG"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["operation_id"] is None and response.json()["changes"] == []
    assert db_session.query(StockMovement).count() == before


def test_correct_takes_the_difference_from_the_oldest_lot_first(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    _receive(client, headers, sizes["1 kg"].id, main.id, 30)
    _receive(client, headers, sizes["1 kg"].id, main.id, 20)
    response = client.post(
        f"{BASE}/admin/products/{product.id}/correct",
        json={"physical_amount": "40", "amount_unit": "KG"},
        headers=headers,
    )
    assert response.status_code == 200
    lots = db_session.query(InventoryLot).order_by(InventoryLot.id).all()
    assert [lot.quantity for lot in lots] == [Decimal("20"), Decimal("20")]  # 10 kg left the older lot


def test_correct_never_goes_below_stock_reserved_for_orders(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    _receive(client, headers, sizes["1 kg"].id, main.id, 50)
    lot = db_session.query(InventoryLot).one()
    lot.reserved_quantity = Decimal("10")
    db_session.commit()

    response = client.post(
        f"{BASE}/admin/products/{product.id}/correct",
        json={"physical_amount": "5", "amount_unit": "KG"},
        headers=headers,
    )
    assert response.status_code == 422
    assert "reserved" in response.json()["message"].lower()
    assert _on_hand_kg(db_session, product.id) == Decimal("50")

    ok = client.post(
        f"{BASE}/admin/products/{product.id}/correct",
        json={"physical_amount": "10", "amount_unit": "KG"},
        headers=headers,
    )
    assert ok.status_code == 200
    assert _on_hand_kg(db_session, product.id) == Decimal("10")


def test_correct_needs_a_warehouse_when_stock_is_in_two(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    second = _location(db_session, "NAG")
    _receive(client, headers, sizes["1 kg"].id, main.id, 30)
    _receive(client, headers, sizes["1 kg"].id, second.id, 20)

    ambiguous = client.post(
        f"{BASE}/admin/products/{product.id}/correct",
        json={"physical_amount": "25", "amount_unit": "KG"},
        headers=headers,
    )
    assert ambiguous.status_code == 422
    assert _on_hand_kg(db_session, product.id) == Decimal("50")

    ok = client.post(
        f"{BASE}/admin/products/{product.id}/correct",
        json={"physical_amount": "25", "amount_unit": "KG", "location_id": main.id},
        headers=headers,
    )
    assert ok.status_code == 200
    assert _on_hand_kg(db_session, product.id, main.id) == Decimal("25")
    assert _on_hand_kg(db_session, product.id, second.id) == Decimal("20")


def test_correct_with_no_stock_record_asks_to_add_stock_first(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    response = client.post(
        f"{BASE}/admin/products/{product.id}/correct",
        json={"physical_amount": "5", "amount_unit": "KG"},
        headers=headers,
    )
    assert response.status_code == 422
    assert db_session.query(StockMovement).count() == 0


def test_correct_rolls_back_everything_when_a_movement_fails(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    _receive(client, headers, sizes["1 kg"].id, main.id, 30)
    _receive(client, headers, sizes["1 kg"].id, main.id, 20)
    before = (db_session.query(StockMovement).count(), db_session.query(AdminActionLog).count())

    real = InventoryService.apply_movement_base
    calls = {"n": 0}

    def flaky(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real(self, *args, **kwargs)

    with patch.object(InventoryService, "apply_movement_base", flaky):
        response = client.post(
            f"{BASE}/admin/products/{product.id}/correct",
            json={"physical_amount": "10", "amount_unit": "KG"},  # needs both lots
            headers=headers,
        )
    assert response.status_code >= 500
    db_session.expire_all()
    assert _on_hand_kg(db_session, product.id) == Decimal("50")
    assert (db_session.query(StockMovement).count(), db_session.query(AdminActionLog).count()) == before


# --------------------------------------------------------------------------
# Remove stock
# --------------------------------------------------------------------------


def test_remove_records_the_reason_and_the_right_movement_type(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    _receive(client, headers, sizes["1 kg"].id, main.id, 50)

    damaged = client.post(
        f"{BASE}/admin/products/{product.id}/remove",
        json={"amount": "2", "amount_unit": "KG", "reason": "Damaged"},
        headers=headers,
    )
    assert damaged.status_code == 200, damaged.text
    assert Decimal(damaged.json()["difference"]) == Decimal("-2")
    expired = client.post(
        f"{BASE}/admin/products/{product.id}/remove",
        json={"amount": "1", "amount_unit": "KG", "reason": "Expired"},
        headers=headers,
    )
    assert expired.status_code == 200
    assert _on_hand_kg(db_session, product.id) == Decimal("47")
    types = [m.movement_type for m in db_session.query(StockMovement).filter(StockMovement.reference_type == "product_remove").order_by(StockMovement.id)]
    assert types == ["DAMAGE", "WASTE"]
    assert "Damaged" in db_session.get(AdminActionLog, damaged.json()["operation_id"]).reason


def test_remove_cannot_touch_reserved_stock(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    _receive(client, headers, sizes["1 kg"].id, main.id, 10)
    lot = db_session.query(InventoryLot).one()
    lot.reserved_quantity = Decimal("8")
    db_session.commit()

    too_much = client.post(
        f"{BASE}/admin/products/{product.id}/remove",
        json={"amount": "5", "amount_unit": "KG", "reason": "Damaged"},
        headers=headers,
    )
    assert too_much.status_code == 422
    assert _on_hand_kg(db_session, product.id) == Decimal("10")
    fine = client.post(
        f"{BASE}/admin/products/{product.id}/remove",
        json={"amount": "2", "amount_unit": "KG", "reason": "Damaged"},
        headers=headers,
    )
    assert fine.status_code == 200
    db_session.expire_all()
    lot = db_session.query(InventoryLot).one()
    assert lot.quantity == Decimal("8") and lot.reserved_quantity == Decimal("8")


def test_remove_spans_lots_oldest_first_and_works_in_grams(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    _receive(client, headers, sizes["1 kg"].id, main.id, 3)
    _receive(client, headers, sizes["1 kg"].id, main.id, 10)
    response = client.post(
        f"{BASE}/admin/products/{product.id}/remove",
        json={"amount": "4500", "amount_unit": "G", "reason": "Waste"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    lots = db_session.query(InventoryLot).order_by(InventoryLot.id).all()
    assert [lot.quantity for lot in lots] == [Decimal("0"), Decimal("8.5")]
    assert lots[0].status == "DEPLETED"
    assert len(response.json()["changes"]) == 2


def test_remove_rolls_back_on_failure(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    _receive(client, headers, sizes["1 kg"].id, main.id, 3)
    _receive(client, headers, sizes["1 kg"].id, main.id, 10)
    real = InventoryService.apply_movement_base
    calls = {"n": 0}

    def flaky(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real(self, *args, **kwargs)

    with patch.object(InventoryService, "apply_movement_base", flaky):
        response = client.post(
            f"{BASE}/admin/products/{product.id}/remove",
            json={"amount": "5", "amount_unit": "KG", "reason": "Damaged"},
            headers=headers,
        )
    assert response.status_code >= 500
    assert _on_hand_kg(db_session, product.id) == Decimal("13")


def test_remove_rejects_units_the_product_cannot_use(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    _receive(client, headers, sizes["1 kg"].id, main.id, 10)
    response = client.post(
        f"{BASE}/admin/products/{product.id}/remove",
        json={"amount": "2", "amount_unit": "L", "reason": "Damaged"},
        headers=headers,
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Move stock
# --------------------------------------------------------------------------


def test_move_shifts_stock_between_warehouses_atomically(client, db_session) -> None:
    admin, headers, product, sizes, main = _setup(db_session, client)
    nagpur = _location(db_session, "NAG")
    _receive(client, headers, sizes["1 kg"].id, main.id, 50)

    response = client.post(
        f"{BASE}/admin/products/{product.id}/move",
        json={"amount": "10", "amount_unit": "KG", "from_location_id": main.id, "to_location_id": nagpur.id},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert _on_hand_kg(db_session, product.id, main.id) == Decimal("40")
    assert _on_hand_kg(db_session, product.id, nagpur.id) == Decimal("10")
    assert _on_hand_kg(db_session, product.id) == Decimal("50")  # nothing created or lost
    kinds = sorted(m.movement_type for m in db_session.query(StockMovement).filter(StockMovement.reference_type == "product_move"))
    assert kinds == ["TRANSFER_IN", "TRANSFER_OUT"]
    warehouses = {w["location_name"]: Decimal(w["amount"]) for w in response.json()["product"]["warehouses"]}
    assert warehouses == {main.name: Decimal("40"), nagpur.name: Decimal("10")}
    # Same delivery, so batch/expiry follows the stock.
    assert len({lot.batch_id for lot in db_session.query(InventoryLot)}) == 1


def test_move_validates_warehouses_and_amount(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    nagpur = _location(db_session, "NAG")
    closed = _location(db_session, "OLD", status="INACTIVE")
    _receive(client, headers, sizes["1 kg"].id, main.id, 5)

    def move(amount, to):
        return client.post(
            f"{BASE}/admin/products/{product.id}/move",
            json={"amount": str(amount), "amount_unit": "KG", "from_location_id": main.id, "to_location_id": to},
            headers=headers,
        )

    assert move(1, main.id).status_code == 422  # same warehouse
    assert move(9, nagpur.id).status_code == 422  # more than there is
    assert move(1, closed.id).status_code == 422  # inactive destination
    assert move(1, 999999).status_code == 404
    assert _on_hand_kg(db_session, product.id, main.id) == Decimal("5")


def test_move_respects_reserved_stock_and_spans_lots(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    nagpur = _location(db_session, "NAG")
    _receive(client, headers, sizes["1 kg"].id, main.id, 4)
    _receive(client, headers, sizes["1 kg"].id, main.id, 6)
    first = db_session.query(InventoryLot).order_by(InventoryLot.id).first()
    first.reserved_quantity = Decimal("3")
    db_session.commit()

    blocked = client.post(
        f"{BASE}/admin/products/{product.id}/move",
        json={"amount": "8", "amount_unit": "KG", "from_location_id": main.id, "to_location_id": nagpur.id},
        headers=headers,
    )
    assert blocked.status_code == 422  # only 7 kg is free

    ok = client.post(
        f"{BASE}/admin/products/{product.id}/move",
        json={"amount": "5", "amount_unit": "KG", "from_location_id": main.id, "to_location_id": nagpur.id},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    db_session.expire_all()
    first = db_session.query(InventoryLot).order_by(InventoryLot.id).first()
    assert first.quantity == Decimal("3") and first.reserved_quantity == Decimal("3")  # free kg moved, reserved stayed
    assert _on_hand_kg(db_session, product.id, nagpur.id) == Decimal("5")


def test_move_rolls_back_on_failure(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    nagpur = _location(db_session, "NAG")
    _receive(client, headers, sizes["1 kg"].id, main.id, 5)
    real = InventoryService.apply_movement_base
    calls = {"n": 0}

    def flaky(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:  # the TRANSFER_IN
            raise RuntimeError("boom")
        return real(self, *args, **kwargs)

    with patch.object(InventoryService, "apply_movement_base", flaky):
        response = client.post(
            f"{BASE}/admin/products/{product.id}/move",
            json={"amount": "2", "amount_unit": "KG", "from_location_id": main.id, "to_location_id": nagpur.id},
            headers=headers,
        )
    assert response.status_code >= 500
    assert _on_hand_kg(db_session, product.id, main.id) == Decimal("5")
    assert db_session.query(InventoryLot).filter(InventoryLot.location_id == nagpur.id).count() == 0


# --------------------------------------------------------------------------
# Undo
# --------------------------------------------------------------------------


def test_undo_reverses_a_removal_with_compensating_movements_only(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    _receive(client, headers, sizes["1 kg"].id, main.id, 50)
    removed = client.post(
        f"{BASE}/admin/products/{product.id}/remove",
        json={"amount": "2", "amount_unit": "KG", "reason": "Damaged"},
        headers=headers,
    ).json()
    originals = db_session.query(StockMovement).count()

    undone = client.post(f"{BASE}/admin/stock-actions/{removed['operation_id']}/undo", headers=headers)
    assert undone.status_code == 200, undone.text
    assert _on_hand_kg(db_session, product.id) == Decimal("50")
    db_session.expire_all()
    assert db_session.query(StockMovement).count() == originals + 1  # history kept, one added
    assert db_session.query(StockMovement).filter(StockMovement.reference_type == "product_remove").count() == 1
    assert db_session.query(AdminActionLog).filter(AdminActionLog.action == "inventory.undo").count() == 1

    again = client.post(f"{BASE}/admin/stock-actions/{removed['operation_id']}/undo", headers=headers)
    assert again.status_code == 409
    assert _on_hand_kg(db_session, product.id) == Decimal("50")


def test_undo_of_a_move_is_refused_once_the_moved_stock_is_reserved(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    nagpur = _location(db_session, "NAG")
    _receive(client, headers, sizes["1 kg"].id, main.id, 20)
    moved = client.post(
        f"{BASE}/admin/products/{product.id}/move",
        json={"amount": "10", "amount_unit": "KG", "from_location_id": main.id, "to_location_id": nagpur.id},
        headers=headers,
    ).json()
    destination = db_session.query(InventoryLot).filter(InventoryLot.location_id == nagpur.id).one()
    destination.reserved_quantity = Decimal("4")  # an order now holds some of it
    db_session.commit()

    refused = client.post(f"{BASE}/admin/stock-actions/{moved['operation_id']}/undo", headers=headers)
    assert refused.status_code == 409
    assert "no longer be undone" in refused.json()["message"]
    assert _on_hand_kg(db_session, product.id, main.id) == Decimal("10")
    assert _on_hand_kg(db_session, product.id, nagpur.id) == Decimal("10")


def test_undo_of_a_correction_restores_the_count(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    _receive(client, headers, sizes["1 kg"].id, main.id, 30)
    _receive(client, headers, sizes["1 kg"].id, main.id, 20)
    corrected = client.post(
        f"{BASE}/admin/products/{product.id}/correct",
        json={"physical_amount": "40", "amount_unit": "KG"},
        headers=headers,
    ).json()
    undone = client.post(f"{BASE}/admin/stock-actions/{corrected['operation_id']}/undo", headers=headers)
    assert undone.status_code == 200
    db_session.expire_all()
    assert [lot.quantity for lot in db_session.query(InventoryLot).order_by(InventoryLot.id)] == [Decimal("30"), Decimal("20")]


def test_undo_is_limited_to_the_same_person_and_a_short_time(client, db_session) -> None:
    admin, headers, product, sizes, main = _setup(db_session, client)
    _receive(client, headers, sizes["1 kg"].id, main.id, 20)
    hub, hub_headers = _user(db_session, HUB_STAFF, "hub@example.com")
    removed = client.post(
        f"{BASE}/admin/products/{product.id}/remove",
        json={"amount": "2", "amount_unit": "KG", "reason": "Damaged"},
        headers=hub_headers,
    ).json()

    other, other_headers = _user(db_session, OPERATIONS, "ops@example.com")
    assert client.post(f"{BASE}/admin/stock-actions/{removed['operation_id']}/undo", headers=other_headers).status_code == 403

    log = db_session.get(AdminActionLog, removed["operation_id"])
    log.created_at = datetime.now(UTC) - timedelta(hours=2)
    db_session.commit()
    assert client.post(f"{BASE}/admin/stock-actions/{removed['operation_id']}/undo", headers=hub_headers).status_code == 409
    assert _on_hand_kg(db_session, product.id) == Decimal("18")
    assert client.post(f"{BASE}/admin/stock-actions/999999/undo", headers=headers).status_code == 404


# --------------------------------------------------------------------------
# Authorization
# --------------------------------------------------------------------------


def test_stock_actions_are_limited_to_the_inventory_roles(client, db_session) -> None:
    _, admin_headers, product, sizes, main = _setup(db_session, client)
    _receive(client, admin_headers, sizes["1 kg"].id, main.id, 10)
    nagpur = _location(db_session, "NAG")
    requests = [
        ("correct", {"physical_amount": "5", "amount_unit": "KG"}),
        ("remove", {"amount": "1", "amount_unit": "KG", "reason": "Damaged"}),
        ("move", {"amount": "1", "amount_unit": "KG", "from_location_id": main.id, "to_location_id": nagpur.id}),
    ]
    for role in (CATALOG_STAFF, CUSTOMER):
        _, headers = _user(db_session, role, f"{role.lower()}@example.com")
        for action, body in requests:
            response = client.post(f"{BASE}/admin/products/{product.id}/{action}", json=body, headers=headers)
            assert response.status_code == 403, (role, action)
    for action, body in requests:
        assert client.post(f"{BASE}/admin/products/{product.id}/{action}", json=body).status_code == 401
    assert _on_hand_kg(db_session, product.id) == Decimal("10")

    for role in (HUB_STAFF, OPERATIONS):
        _, headers = _user(db_session, role, f"{role.lower()}2@example.com")
        assert client.post(
            f"{BASE}/admin/products/{product.id}/remove",
            json={"amount": "1", "amount_unit": "KG", "reason": "Damaged"},
            headers=headers,
        ).status_code == 200


# --------------------------------------------------------------------------
# The Inventory page data
# --------------------------------------------------------------------------


def test_stock_cards_report_status_warehouses_expiry_and_reserved(client, db_session) -> None:
    _, headers, product, sizes, main = _setup(db_session, client)
    nagpur = _location(db_session, "NAG")
    _receive(client, headers, sizes["1 kg"].id, main.id, 35, expiry_date=(business_today() + timedelta(days=2)).isoformat())
    _receive(client, headers, sizes["1 kg"].id, nagpur.id, 15)
    lot = db_session.query(InventoryLot).order_by(InventoryLot.id).first()
    lot.reserved_quantity = Decimal("5")
    db_session.commit()

    cards = client.get(f"{BASE}/admin/products", headers=headers).json()["items"]
    card = next(c for c in cards if c["product_id"] == product.id)
    total = card["totals"][0]
    assert (Decimal(total["amount"]), Decimal(total["reserved_amount"]), Decimal(total["on_hand_amount"])) == (
        Decimal("45"), Decimal("5"), Decimal("50"),
    )
    assert {w["location_name"]: Decimal(w["amount"]) for w in card["warehouses"]} == {
        main.name: Decimal("30"), nagpur.name: Decimal("15"),
    }
    assert card["expiry"]["days_left"] == 2 and card["stock_status"] == "OK"


def test_stock_filters_and_summary_count_low_out_and_expiring(client, db_session) -> None:
    _, headers, tomato, sizes, main = _setup(db_session, client)
    category = db_session.query(Category).first()
    potato = Product(category_id=category.id, name="Potato", slug="potato", status="ACTIVE")
    onion = Product(category_id=category.id, name="Onion", slug="onion", status="ACTIVE")
    db_session.add_all([potato, onion])
    db_session.commit()
    pv = ProductVariant(product_id=potato.id, name="1 kg", sku="POTATO-1KG", unit="KG", quantity=Decimal("1"), status="ACTIVE")
    ov = ProductVariant(product_id=onion.id, name="1 kg", sku="ONION-1KG", unit="KG", quantity=Decimal("1"), status="ACTIVE")
    db_session.add_all([pv, ov])
    db_session.commit()
    _receive(client, headers, sizes["1 kg"].id, main.id, 50, expiry_date=(business_today() + timedelta(days=3)).isoformat())
    _receive(client, headers, pv.id, main.id, 8)  # at/below the default reserve of 10 packs

    summary = client.get(f"{BASE}/admin/products/summary", headers=headers).json()
    assert summary == {"all": 3, "low": 1, "out": 1, "expiring": 1}

    def names(status):
        items = client.get(f"{BASE}/admin/products", params={"status": status}, headers=headers).json()
        return [i["product_name"] for i in items["items"]]

    assert names("low") == ["Potato"]
    assert names("out") == ["Onion"]
    assert names("expiring") == ["Tomato"]
    assert sorted(names("all")) == ["Onion", "Potato", "Tomato"]
    assert client.get(f"{BASE}/admin/products", params={"status": "bogus"}, headers=headers).status_code == 422
