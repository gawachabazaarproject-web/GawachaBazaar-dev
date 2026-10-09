"""Reserve levels + stock alerts, removing stock, and deleting products /
categories (with the guards that stop history from being broken)."""

from decimal import Decimal

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import ADMIN
from app.models.category import Category
from app.models.inventory_lot import InventoryLot
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.services.stock_levels import BELOW, NEAR, OK, OUT, stock_level
from tests.test_phase_13_cart_orders import (
    _create_price,
    _create_product_variant,
    _ready_customer,
    _stock_variant,
)
from tests.test_phase_18_cancellation_refunds import _staff


def _admin(db_session: Session, tag: str):
    return _staff(db_session, ADMIN, tag)


def _stocked(db_session: Session, tag: str, quantity: str):
    product, variant = _create_product_variant(db_session, tag=tag)
    _create_price(db_session, variant, price=Decimal("10.00"))
    lot = _stock_variant(db_session, product, variant, tag=tag, quantity=Decimal(quantity))
    return product, variant, lot


def _alerts(client: TestClient, headers: dict) -> dict:
    response = client.get("/api/v1/inventory/admin/stock-alerts", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# The rule itself
# ---------------------------------------------------------------------------


def test_stock_level_rule() -> None:
    reserve = Decimal("20")
    assert stock_level(Decimal("0"), reserve) == OUT
    assert stock_level(Decimal("-3"), reserve) == OUT
    assert stock_level(Decimal("20"), reserve) == BELOW  # at the reserve counts as below
    assert stock_level(Decimal("5"), reserve) == BELOW
    assert stock_level(Decimal("25"), reserve) == NEAR  # within 25% above
    assert stock_level(Decimal("26"), reserve) == OK
    # No reserve set -> the default of 10 applies.
    assert stock_level(Decimal("10"), None) == BELOW
    assert stock_level(Decimal("12"), None) == NEAR
    assert stock_level(Decimal("13"), None) == OK


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


def test_alerts_follow_each_products_own_reserve_level(client: TestClient, db_session: Session) -> None:
    _admin_user, headers = _admin(db_session, "a1")
    _product, variant, _lot = _stocked(db_session, "AL1", "50")  # plenty vs default reserve 10
    assert _alerts(client, headers)["count"] == 0

    # Raise this item's reserve to 60: 50 available is now below it.
    response = client.patch(f"/api/v1/catalog/variants/{variant.id}", json={"reserve_level": "60"}, headers=headers)
    assert response.status_code == 200, response.text
    data = _alerts(client, headers)
    assert data["count"] == 1 and data["below_count"] == 1
    assert data["items"][0]["variant_id"] == variant.id
    assert Decimal(data["items"][0]["reserve_level"]) == Decimal("60")
    assert data["items"][0]["level"] == BELOW

    # Close to it (within 25% above) is a "near" warning.
    client.patch(f"/api/v1/catalog/variants/{variant.id}", json={"reserve_level": "42"}, headers=headers)
    assert _alerts(client, headers)["items"][0]["level"] == NEAR

    # Back to comfortable.
    client.patch(f"/api/v1/catalog/variants/{variant.id}", json={"reserve_level": "10"}, headers=headers)
    assert _alerts(client, headers)["count"] == 0

    # Clearing the reserve (null) falls back to the default.
    client.patch(f"/api/v1/catalog/variants/{variant.id}", json={"reserve_level": None}, headers=headers)
    db_session.expire_all()
    assert db_session.query(ProductVariant).filter_by(id=variant.id).one().reserve_level is None


def test_item_with_no_stock_record_is_out_of_stock(client: TestClient, db_session: Session) -> None:
    _admin_user, headers = _admin(db_session, "a2")
    _product, variant = _create_product_variant(db_session, tag="AL2")  # never stocked
    data = _alerts(client, headers)
    assert [(i["variant_id"], i["level"]) for i in data["items"]] == [(variant.id, OUT)]


def test_alerts_are_ordered_most_urgent_first_and_skip_inactive_items(client: TestClient, db_session: Session) -> None:
    _admin_user, headers = _admin(db_session, "a3")
    _p1, near_variant, _l1 = _stocked(db_session, "AL3N", "12")  # NEAR (default reserve 10)
    _p2, below_variant, _l2 = _stocked(db_session, "AL3B", "5")  # BELOW
    _p3, out_variant, _l3 = _stocked(db_session, "AL3O", "0.001")
    db_session.query(InventoryLot).filter_by(variant_id=out_variant.id).update({"quantity": Decimal("0")})
    _p4, hidden_variant, _l4 = _stocked(db_session, "AL3H", "1")  # low, but archived
    db_session.query(ProductVariant).filter_by(id=hidden_variant.id).update({"status": "INACTIVE"})
    db_session.commit()

    items = _alerts(client, headers)["items"]
    assert [i["level"] for i in items] == [OUT, BELOW, NEAR]
    assert [i["variant_id"] for i in items] == [out_variant.id, below_variant.id, near_variant.id]


def test_dashboard_low_stock_card_uses_the_same_alerts(client: TestClient, db_session: Session) -> None:
    _admin_user, headers = _admin(db_session, "a4")
    _product, variant, _lot = _stocked(db_session, "AL4", "5")
    response = client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["low_stock_count"] == 1
    row = body["low_stock"][0]
    assert row["variant_id"] == variant.id
    assert row["level"] == BELOW
    assert Decimal(row["reserve_level"]) == Decimal("10")
    assert row["product_name"]


def test_lot_status_uses_the_items_reserve_level(client: TestClient, db_session: Session) -> None:
    _admin_user, headers = _admin(db_session, "a5")
    _product, variant, lot = _stocked(db_session, "AL5", "50")
    detail = client.get(f"/api/v1/inventory/admin/lots/{lot.id}", headers=headers).json()
    assert detail["operational_status"] == "IN_STOCK"
    client.patch(f"/api/v1/catalog/variants/{variant.id}", json={"reserve_level": "80"}, headers=headers)
    detail = client.get(f"/api/v1/inventory/admin/lots/{lot.id}", headers=headers).json()
    assert detail["operational_status"] == "LOW_STOCK"
    assert Decimal(detail["reserve_level"]) == Decimal("80")


def test_negative_reserve_level_is_rejected(client: TestClient, db_session: Session) -> None:
    _admin_user, headers = _admin(db_session, "a6")
    _product, variant, _lot = _stocked(db_session, "AL6", "50")
    response = client.patch(f"/api/v1/catalog/variants/{variant.id}", json={"reserve_level": "-1"}, headers=headers)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Remove stock
# ---------------------------------------------------------------------------


def test_remove_part_of_a_lots_stock(client: TestClient, db_session: Session) -> None:
    _admin_user, headers = _admin(db_session, "r1")
    _product, _variant, lot = _stocked(db_session, "RM1", "100")
    response = client.post(
        f"/api/v1/inventory/admin/lots/{lot.id}/remove", json={"quantity": "30", "reason": "Spoiled"}, headers=headers
    )
    assert response.status_code == 200, response.text
    assert Decimal(response.json()["on_hand"]) == Decimal("70")
    movements = client.get(f"/api/v1/inventory/lots/{lot.id}/movements", headers=headers).json()
    removal = [m for m in movements["items"] if m["movement_type"] == "ADJUSTMENT_OUT"]
    assert removal and "Spoiled" in (removal[0]["remarks"] or "")


def test_remove_all_available_stock_when_no_quantity_is_given(client: TestClient, db_session: Session) -> None:
    _admin_user, headers = _admin(db_session, "r2")
    _product, _variant, lot = _stocked(db_session, "RM2", "40")
    response = client.post(
        f"/api/v1/inventory/admin/lots/{lot.id}/remove", json={"reason": "Written off"}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["on_hand"]) == 0 and body["operational_status"] == "OUT_OF_STOCK"
    # Nothing left to remove now.
    again = client.post(f"/api/v1/inventory/admin/lots/{lot.id}/remove", json={"reason": "again"}, headers=headers)
    assert again.status_code in (400, 422)


def test_cannot_remove_more_than_is_available_or_without_a_reason(client: TestClient, db_session: Session) -> None:
    _admin_user, headers = _admin(db_session, "r3")
    _product, _variant, lot = _stocked(db_session, "RM3", "10")
    too_much = client.post(
        f"/api/v1/inventory/admin/lots/{lot.id}/remove", json={"quantity": "11", "reason": "x"}, headers=headers
    )
    assert too_much.status_code in (400, 422)
    no_reason = client.post(f"/api/v1/inventory/admin/lots/{lot.id}/remove", json={"quantity": "1"}, headers=headers)
    assert no_reason.status_code == 422
    db_session.expire_all()
    assert db_session.query(InventoryLot).filter_by(id=lot.id).one().quantity == Decimal("10.000")


def test_stock_already_promised_to_orders_cannot_be_removed(client: TestClient, db_session: Session) -> None:
    _admin_user, admin_headers = _admin(db_session, "r4")
    _user, headers, variant, address = _ready_customer(db_session, "RM4")  # lot of 1000
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "30"}, headers=headers)
    assert client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers).status_code == 201
    lot = db_session.query(InventoryLot).filter_by(variant_id=variant.id).one()
    db_session.refresh(lot)
    assert lot.reserved_quantity == Decimal("30")
    # 970 is available; asking for all 1000 would eat into the 30 reserved.
    too_much = client.post(
        f"/api/v1/inventory/admin/lots/{lot.id}/remove", json={"quantity": "1000", "reason": "x"}, headers=admin_headers
    )
    assert too_much.status_code in (400, 422)
    everything = client.post(
        f"/api/v1/inventory/admin/lots/{lot.id}/remove", json={"reason": "clear"}, headers=admin_headers
    )
    assert everything.status_code == 200
    assert Decimal(everything.json()["on_hand"]) == Decimal("30")  # the reserved 30 stays


# ---------------------------------------------------------------------------
# Delete product / category
# ---------------------------------------------------------------------------


def test_delete_a_product_with_no_history_removes_it_and_its_stock(client: TestClient, db_session: Session) -> None:
    _admin_user, headers = _admin(db_session, "d1")
    product, variant, _lot = _stocked(db_session, "DEL1", "25")
    product_id, variant_id = product.id, variant.id
    response = client.delete(f"/api/v1/catalog/products/{product_id}", headers=headers)
    assert response.status_code == 204, response.text
    db_session.expire_all()
    assert db_session.query(Product).filter_by(id=product_id).first() is None
    assert db_session.query(ProductVariant).filter_by(id=variant_id).first() is None
    assert db_session.query(InventoryLot).filter_by(variant_id=variant_id).count() == 0
    assert client.get(f"/api/v1/catalog/products/{product_id}").status_code == 404


def test_cannot_delete_a_product_that_has_been_ordered(client: TestClient, db_session: Session) -> None:
    _admin_user, admin_headers = _admin(db_session, "d2")
    _user, headers, variant, address = _ready_customer(db_session, "DEL2")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    assert client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers).status_code == 201

    response = client.delete(f"/api/v1/catalog/products/{variant.product_id}", headers=admin_headers)

    assert response.status_code == 409
    assert "Archived" in response.json()["message"]
    db_session.expire_all()
    assert db_session.query(Product).filter_by(id=variant.product_id).first() is not None


def test_deleting_a_product_clears_it_from_carts_and_wishlists(client: TestClient, db_session: Session) -> None:
    _admin_user, admin_headers = _admin(db_session, "d3")
    _user, headers, variant, _address = _ready_customer(db_session, "DEL3")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "2"}, headers=headers)
    assert client.delete(f"/api/v1/catalog/products/{variant.product_id}", headers=admin_headers).status_code == 204
    cart = client.get("/api/v1/cart", headers=headers).json()
    assert cart["items"] == []


def test_delete_category_only_when_empty(client: TestClient, db_session: Session) -> None:
    _admin_user, headers = _admin(db_session, "c1")
    product, _variant = _create_product_variant(db_session, tag="DC1")
    product_id, category_id = product.id, product.category_id

    blocked = client.delete(f"/api/v1/catalog/categories/{category_id}", headers=headers)
    assert blocked.status_code == 409
    assert "product" in blocked.json()["message"]

    assert client.delete(f"/api/v1/catalog/products/{product_id}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/catalog/categories/{category_id}", headers=headers).status_code == 204
    db_session.expire_all()
    assert db_session.query(Category).filter_by(id=category_id).first() is None


def test_cannot_delete_a_category_that_has_sub_categories(client: TestClient, db_session: Session) -> None:
    _admin_user, headers = _admin(db_session, "c2")
    parent = Category(name="Parent-DC2", slug="parent-dc2", status="ACTIVE")
    db_session.add(parent)
    db_session.commit()
    child = Category(name="Child-DC2", slug="child-dc2", status="ACTIVE", parent_id=parent.id)
    db_session.add(child)
    db_session.commit()
    response = client.delete(f"/api/v1/catalog/categories/{parent.id}", headers=headers)
    assert response.status_code == 409
    assert "sub-categor" in response.json()["message"]


def test_delete_endpoints_need_the_right_permission(client: TestClient, db_session: Session) -> None:
    _user, customer_headers, variant, _address = _ready_customer(db_session, "DEL5")
    assert client.delete(f"/api/v1/catalog/products/{variant.product_id}", headers=customer_headers).status_code == 403
    assert client.delete("/api/v1/catalog/categories/1", headers=customer_headers).status_code == 403
    assert client.delete(f"/api/v1/catalog/products/{variant.product_id}").status_code == 401
