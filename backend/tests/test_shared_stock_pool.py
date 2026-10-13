"""Shared stock pool across the size variants of one product.

Pure-arithmetic tests need no database. The DB tests reuse the Phase 15
fixtures/helpers and, like them, run against real PostgreSQL.
"""

from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.models.inventory_lot import InventoryLot
from app.models.inventory_reservation_item import InventoryReservationItem
from app.models.product_variant import ProductVariant
from app.services.stock_pool import (
    available_packs_by_variant,
    to_packs,
    variant_size,
)
from tests.test_phase_15_inventory_reservation_fulfillment import (
    _checkout,
    _create_address,
    _create_lot,
    _create_price,
    _create_product_variant,
    _customer,
)


def _v(unit: str, quantity: str) -> SimpleNamespace:
    return SimpleNamespace(unit=unit, quantity=Decimal(quantity))


def test_variant_size_converts_within_a_unit_family() -> None:
    assert variant_size(_v("KG", "1")) == ("MASS", Decimal("1000"))
    assert variant_size(_v("G", "250")) == ("MASS", Decimal("250"))
    assert variant_size(_v("KG", "0.25")) == ("MASS", Decimal("250.00"))
    assert variant_size(_v("DOZEN", "1"))[0] == variant_size(_v("UNIT", "6"))[0]
    assert variant_size(_v("PACK", "1"))[0] != variant_size(_v("BOX", "1"))[0]


def test_to_packs_rounds_down() -> None:
    assert to_packs(Decimal("5000"), Decimal("250")) == Decimal("20.000")
    assert to_packs(Decimal("1000"), Decimal("300")) == Decimal("3.333")
    assert to_packs(Decimal("100"), Decimal("250")) == Decimal("0.400")


def _add_variant(db: Session, product_id: int, tag: str, unit: str, qty: str) -> ProductVariant:
    variant = ProductVariant(
        product_id=product_id, name=f"{qty} {unit}", sku=f"SKU-{tag}-{qty}{unit}",
        unit=unit, quantity=Decimal(qty), status="ACTIVE",
    )
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return variant


def test_sibling_without_own_stock_shows_pool_not_zero(db_session: Session) -> None:
    """Chikoo case: stock entered only against 1 kg; 250 g must not read 0."""
    product, kg = _create_product_variant(db_session, tag="POOL1")
    grams = _add_variant(db_session, product.id, "POOL1", "G", "250")
    _create_lot(db_session, product, kg, tag="POOL1", quantity=Decimal("5.000"))

    stock = available_packs_by_variant(db_session, [kg.id, grams.id])
    assert stock[kg.id] == Decimal("5.000")
    assert stock[grams.id] == Decimal("20.000")


def test_checkout_of_small_size_draws_from_big_size_lot(
    client: TestClient, db_session: Session
) -> None:
    user, headers = _customer(db_session, "POOL2")
    product, kg = _create_product_variant(db_session, tag="POOL2")
    grams = _add_variant(db_session, product.id, "POOL2", "G", "250")
    _create_price(db_session, grams)
    lot = _create_lot(db_session, product, kg, tag="POOL2", quantity=Decimal("5.000"))
    address = _create_address(db_session, user)

    order = _checkout(client, headers, grams, address, qty="4")

    db_session.expire_all()
    refreshed = db_session.get(InventoryLot, lot.id)
    assert refreshed.reserved_quantity == Decimal("1.000")  # 4 x 250 g = 1 kg
    rows = (
        db_session.query(InventoryReservationItem)
        .filter(InventoryReservationItem.inventory_lot_id == lot.id)
        .all()
    )
    assert [r.quantity for r in rows] == [Decimal("1.000")]
    assert order["id"]

    stock = available_packs_by_variant(db_session, [kg.id, grams.id])
    assert stock[kg.id] == Decimal("4.000")
    assert stock[grams.id] == Decimal("16.000")
