"""Admin dashboard (GET /api/v1/dashboard).

Builds a realistic "today" through the real API - an unpicked order, one
out for delivery (stalled), one delivered with COD cash collected, one
cancelled, plus yesterday's order and a low-stock product - and checks
every number the Admin panel's home page shows.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import ADMIN, HUB_STAFF, OPERATIONS
from app.models.fulfillment import Fulfillment
from app.models.order import Order
from app.services.dashboard import business_day_start
from tests.test_phase_14_payments import _create_order
from tests.test_phase_16_fulfillment_delivery import (
    _assign_and_dispatch,
    _checkout,
    _confirm_cod_and_get_fulfillment_id,
    _create_lot,
    _create_product_variant,
    _full_cod_ready_for_delivery,
    _ready_customer,
    _staff,
)


def test_business_day_is_india_standard_time() -> None:
    # 20:00 UTC on the 26th is already 01:30 IST on the 27th.
    assert business_day_start(datetime(2026, 9, 26, 20, 0, tzinfo=UTC)) == datetime(2026, 9, 26, 18, 30, tzinfo=UTC)
    # 17:00 UTC on the 26th is 22:30 IST the same day.
    assert business_day_start(datetime(2026, 9, 26, 17, 0, tzinfo=UTC)) == datetime(2026, 9, 25, 18, 30, tzinfo=UTC)


def test_dashboard_reflects_todays_operations(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)

    # A: confirmed an hour ago, picking never started -> "needs attention".
    _u, headers_a, variant_a, address_a, _lot = _ready_customer(db_session, "DA")
    order_a = _checkout(client, headers_a, variant_a, address_a, qty="2")
    fulfillment_a = _confirm_cod_and_get_fulfillment_id(client, db_session, headers_a, order_a["id"])

    # B: out for delivery for 4 hours -> "delivery issue".
    order_b, fulfillment_b, ops_headers, _lot_b, _q = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="DB"
    )
    _assign_and_dispatch(client, db_session, ops_headers, fulfillment_b, "DB")

    # C: delivered today, COD cash collected -> counts as collected money.
    order_c, fulfillment_c, ops_headers_c, _lot_c, _q = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="DC"
    )
    _partner, partner_headers = _assign_and_dispatch(client, db_session, ops_headers_c, fulfillment_c, "DC")
    assert client.post(f"/api/v1/fulfillments/{fulfillment_c}/deliver", headers=partner_headers).status_code == 200

    # D: placed and cancelled today.
    _u, headers_d, variant_d, address_d, _lot = _ready_customer(db_session, "DD")
    order_d = _checkout(client, headers_d, variant_d, address_d)
    assert client.post(f"/api/v1/orders/{order_d['id']}/cancel", json={}, headers=headers_d).status_code == 200

    # Yesterday's order must not count as "today".
    old_user, _h = _staff(db_session, "CUSTOMER", "DOLD")
    old = _create_order(db_session, old_user)
    old.placed_at = now - timedelta(days=2)

    # A product running low (4 < threshold 10) across its only lot.
    product, variant_low = _create_product_variant(db_session, tag="DLOW")
    _create_lot(db_session, product, variant_low, tag="DLOW", quantity=Decimal("4.000"))

    db_session.execute(
        update(Fulfillment).where(Fulfillment.id == fulfillment_a).values(created_at=now - timedelta(hours=1))
    )
    db_session.execute(
        update(Fulfillment).where(Fulfillment.id == fulfillment_b).values(updated_at=now - timedelta(hours=4))
    )
    db_session.commit()

    _admin, admin_headers = _staff(db_session, ADMIN, "DADMIN")
    response = client.get("/api/v1/dashboard", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    tiles = body["tiles"]
    assert tiles["orders_today"] == 4  # A, B, C, D
    assert tiles["to_fulfil"] == 1  # A (B is out, C delivered, D cancelled)
    assert tiles["out_for_delivery"] == 1  # B
    assert tiles["delivered_today"] == 1  # C
    assert tiles["cancelled_today"] == 1  # D
    # Only C's COD cash has actually been collected; A/B are still unpaid COD.
    assert Decimal(tiles["collected_today"]) == Decimal(order_c["total_amount"])

    assert [a["order_id"] for a in body["attention"]] == [order_a["id"]]
    assert [d["fulfillment_id"] for d in body["delivery_issues"]] == [fulfillment_b]
    assert body["delivery_issues"][0]["status"] == "OUT_FOR_DELIVERY"
    assert body["delivery_issues"][0]["delivery_partner_name"]

    assert body["low_stock_count"] == 1
    [low] = body["low_stock"]
    assert low["variant_id"] == variant_low.id
    assert Decimal(low["available"]) == Decimal("4")
    assert body["refunds_pending_approval"] == 0

    db_session.expire_all()
    assert db_session.get(Order, order_b["id"]).status == "CONFIRMED"  # read-only: nothing changed


def test_dashboard_access(client: TestClient, db_session: Session) -> None:
    _ops, ops_headers = _staff(db_session, OPERATIONS, "DACC1")
    _hub, hub_headers = _staff(db_session, HUB_STAFF, "DACC2")
    _customer, customer_headers = _staff(db_session, "CUSTOMER", "DACC3")

    assert client.get("/api/v1/dashboard", headers=ops_headers).status_code == 200
    assert client.get("/api/v1/dashboard", headers=hub_headers).status_code == 403
    assert client.get("/api/v1/dashboard", headers=customer_headers).status_code == 403
    assert client.get("/api/v1/dashboard").status_code == 401
