"""POST /delivery/quote, POST /delivery/geocode and the server-authoritative
fee at checkout. Routing/geocoding are stubbed; the database is real."""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.config import settings
from app.models.address import Address
from app.models.order import Order
from app.services.geocoding.base import GeocodeResult, GeocodingError
from app.services.routing import service as routing_service
from app.services.routing.base import RoutingError
from app.services.routing.cache import route_cache
from tests.test_delivery_fee import StubProvider
from tests.test_phase_13_cart_orders import (
    _create_address,
    _customer,
    _ready_customer,
)

QUOTE = "/api/v1/delivery/quote"


@pytest.fixture
def stub(monkeypatch) -> StubProvider:
    provider = StubProvider(4700)
    monkeypatch.setattr(routing_service, "get_routing_provider", lambda: provider)
    route_cache._local.clear()
    monkeypatch.setattr(settings, "PACKING_POINT_LATITUDE", 21.1458)
    monkeypatch.setattr(settings, "PACKING_POINT_LONGITUDE", 79.0882)
    monkeypatch.setattr(settings, "DELIVERY_BASE_FEE", Decimal("20"))
    monkeypatch.setattr(settings, "DELIVERY_PER_KM", Decimal("10"))
    monkeypatch.setattr(settings, "DELIVERY_MAX_DISTANCE_KM", 0.0)
    monkeypatch.setattr(settings, "DELIVERY_MIN_ORDER_VALUE", Decimal("0"))
    return provider


def _locate(db: Session, address: Address, lat="21.190000", lng="79.110000") -> Address:
    address.latitude, address.longitude = Decimal(lat), Decimal(lng)
    db.commit()
    return address


# --- /delivery/quote -----------------------------------------------------------


def test_quote_requires_authentication(client: TestClient, stub) -> None:
    assert client.post(QUOTE, json={"address_id": 1}).status_code in (401, 403)


def test_quote_valid_address(client: TestClient, db_session: Session, stub) -> None:
    user, headers = _customer(db_session, "Q1")
    address = _locate(db_session, _create_address(db_session, user))
    r = client.post(QUOTE, json={"address_id": address.id}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is True
    assert body["distance_meters"] == 4700 and body["distance_km"] == 4.7
    assert body["estimated_duration_minutes"] == 10  # stub: 600 s
    assert Decimal(body["delivery_fee"]) == Decimal("67")
    assert body["currency"] == "INR"
    # second call is served from the route cache
    client.post(QUOTE, json={"address_id": address.id}, headers=headers)
    assert stub.calls == 1


def test_quote_other_customers_address_is_404(client: TestClient, db_session: Session, stub) -> None:
    owner, _ = _customer(db_session, "Q2OWNER")
    _other, other_headers = _customer(db_session, "Q2OTHER")
    address = _locate(db_session, _create_address(db_session, owner))
    assert client.post(QUOTE, json={"address_id": address.id}, headers=other_headers).status_code == 404


def test_quote_missing_address_is_404(client: TestClient, db_session: Session, stub) -> None:
    _user, headers = _customer(db_session, "Q3")
    assert client.post(QUOTE, json={"address_id": 999999}, headers=headers).status_code == 404


def test_quote_address_without_coordinates_is_422(client: TestClient, db_session: Session, stub) -> None:
    user, headers = _customer(db_session, "Q4")
    address = _create_address(db_session, user)
    assert client.post(QUOTE, json={"address_id": address.id}, headers=headers).status_code == 422
    assert stub.calls == 0


def test_quote_outside_radius(client: TestClient, db_session: Session, stub, monkeypatch) -> None:
    monkeypatch.setattr(settings, "DELIVERY_MAX_DISTANCE_KM", 10.0)
    stub.meters = 14_200
    user, headers = _customer(db_session, "Q5")
    address = _locate(db_session, _create_address(db_session, user))
    r = client.post(QUOTE, json={"address_id": address.id}, headers=headers)
    assert r.status_code == 200
    assert r.json() == {
        "available": False, "distance_km": 14.2, "distance_meters": None,
        "estimated_duration_minutes": None, "delivery_fee": None, "free_delivery": False,
        "currency": "INR", "reason": "Delivery is not available beyond 10 km.",
    }


def test_quote_routing_down_is_503(client: TestClient, db_session: Session, stub) -> None:
    stub.error = RoutingError("down")
    user, headers = _customer(db_session, "Q6")
    address = _locate(db_session, _create_address(db_session, user))
    assert client.post(QUOTE, json={"address_id": address.id}, headers=headers).status_code == 503


def test_quote_origin_not_configured(client: TestClient, db_session: Session, stub, monkeypatch) -> None:
    monkeypatch.setattr(settings, "PACKING_POINT_LATITUDE", None)
    user, headers = _customer(db_session, "Q7")
    address = _locate(db_session, _create_address(db_session, user))
    assert client.post(QUOTE, json={"address_id": address.id}, headers=headers).status_code == 422


def test_quote_rejects_client_supplied_amounts(client: TestClient, db_session: Session, stub) -> None:
    user, headers = _customer(db_session, "Q8")
    address = _locate(db_session, _create_address(db_session, user))
    r = client.post(
        QUOTE, json={"address_id": address.id, "delivery_fee": 1, "distance_km": 0.1}, headers=headers
    )
    assert r.status_code == 200
    assert Decimal(r.json()["delivery_fee"]) == Decimal("67")
    assert r.json()["distance_meters"] == 4700


# --- addresses: coordinate validation + geocode metadata -----------------------


def test_address_rejects_out_of_range_coordinates(client: TestClient, db_session: Session) -> None:
    _user, headers = _customer(db_session, "A1")
    base = {"label": "Home", "address_line_1": "1 Road", "city": "Nagpur",
            "state": "MH", "postal_code": "440001"}
    assert client.post("/api/v1/addresses", json={**base, "latitude": "95", "longitude": "79"},
                       headers=headers).status_code == 422
    assert client.post("/api/v1/addresses", json={**base, "latitude": "21", "longitude": "181"},
                       headers=headers).status_code == 422


def test_address_saves_geocode_metadata(client: TestClient, db_session: Session) -> None:
    _user, headers = _customer(db_session, "A2")
    r = client.post(
        "/api/v1/addresses",
        json={"label": "Home", "address_line_1": "1 Road", "city": "Nagpur", "state": "MH",
              "postal_code": "440001", "latitude": "21.1463", "longitude": "79.0849",
              "geocode_provider_id": "123"},
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    row = db_session.get(Address, r.json()["id"])
    assert row.geocode_provider == "nominatim" and row.geocode_provider_id == "123"
    assert row.geocoded_at is not None


# --- /delivery/geocode ---------------------------------------------------------


def test_geocode_returns_candidates(client: TestClient, db_session: Session, monkeypatch) -> None:
    class Fake:
        def search(self, query, limit=5):
            return [GeocodeResult("Sitabuldi, Nagpur", 21.1463, 79.0849, "nominatim", "123")]

    monkeypatch.setattr("app.api.v1.delivery.get_geocoding_provider", lambda: Fake())
    _user, headers = _customer(db_session, "G1")
    r = client.post("/api/v1/delivery/geocode", json={"query": "Sitabuldi Nagpur"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["items"][0]["provider_id"] == "123"


def test_geocode_unavailable_is_503(client: TestClient, db_session: Session, monkeypatch) -> None:
    class Down:
        def search(self, query, limit=5):
            raise GeocodingError("Address search is unavailable right now.")

    monkeypatch.setattr("app.api.v1.delivery.get_geocoding_provider", lambda: Down())
    _user, headers = _customer(db_session, "G2")
    r = client.post("/api/v1/delivery/geocode", json={"query": "Sitabuldi"}, headers=headers)
    assert r.status_code == 503


def test_geocode_requires_authentication(client: TestClient) -> None:
    assert client.post("/api/v1/delivery/geocode", json={"query": "abc"}).status_code in (401, 403)


# --- checkout: the server alone decides distance and fee -----------------------


def _cart_with_item(client, headers, variant):
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)


def test_checkout_ignores_client_fee_and_stores_route_audit(
    client: TestClient, db_session: Session, stub
) -> None:
    user, headers, variant, address = _ready_customer(db_session, "C1")
    _locate(db_session, address)
    _cart_with_item(client, headers, variant)
    r = client.post(
        "/api/v1/cart/checkout",
        json={"address_id": address.id, "delivery_fee": 1, "distance_km": 0.1,
              "warehouse_id": 999, "total_amount": 1},
        headers=headers,
    )
    # Unknown fields are ignored by the schema: the order is created and the
    # fee is the SERVER's (regression test for client fee tampering).
    assert r.status_code == 201, r.text
    body = r.json()
    assert Decimal(body["delivery_fee"]) == Decimal("67.00")
    assert Decimal(body["total_amount"]) == Decimal("50.00") + Decimal("67.00")
    order = db_session.get(Order, body["id"])
    assert order.delivery_distance_meters == 4700
    assert order.routing_provider == "stub"
    assert order.warehouse_id != 999


def test_checkout_fails_safe_when_routing_down(client: TestClient, db_session: Session, stub) -> None:
    stub.error = RoutingError("down")
    user, headers, variant, address = _ready_customer(db_session, "C2")
    _locate(db_session, address)
    _cart_with_item(client, headers, variant)
    r = client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)
    assert r.status_code == 503
    assert db_session.query(Order).filter_by(user_id=user.id).count() == 0


def test_checkout_refuses_outside_radius(client: TestClient, db_session: Session, stub, monkeypatch) -> None:
    monkeypatch.setattr(settings, "DELIVERY_MAX_DISTANCE_KM", 4.0)
    user, headers, variant, address = _ready_customer(db_session, "C3")
    _locate(db_session, address)
    _cart_with_item(client, headers, variant)
    r = client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)
    assert r.status_code == 422
    assert db_session.query(Order).filter_by(user_id=user.id).count() == 0


def test_checkout_minimum_order_value(client: TestClient, db_session: Session, stub, monkeypatch) -> None:
    monkeypatch.setattr(settings, "DELIVERY_MIN_ORDER_VALUE", Decimal("100"))
    user, headers, variant, address = _ready_customer(db_session, "C4")
    _locate(db_session, address)
    _cart_with_item(client, headers, variant)  # Rs 50 < Rs 100
    r = client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)
    assert r.status_code == 422
