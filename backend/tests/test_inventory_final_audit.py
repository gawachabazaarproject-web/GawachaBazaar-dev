"""Final audit of the base-unit inventory model: real-path rollbacks, per-dimension
lifecycles, shared pool vs shares, quarantine/resolve, API compatibility and guards
against any legacy pack-based write path coming back."""

import re
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import func, text

from app.core.roles import CUSTOMER, HUB_STAFF
from app.exceptions.base import BusinessValidationError, ConflictError
from app.models.admin_action_log import AdminActionLog
from app.models.inventory_lot import InventoryLot
from app.models.stock_movement import StockMovement
from app.schemas.admin_inventory import (
    ProductCorrectStockRequest,
    ProductMoveStockRequest,
    ProductRemoveStockRequest,
    SetStockSharesRequest,
)
from app.services.inventory import InventoryService
from app.services.stock_pool import pool_base_amounts
from tests.test_inventory_base_units import Env
from tests.test_phase_16_fulfillment_delivery import _staff

APP = Path(__file__).resolve().parents[1] / "app"
API = "/api/v1/inventory"


def _books(env: Env) -> tuple:
    return tuple((lot.id, lot.quantity_base, lot.reserved_base) for lot in env.lots())


# ------------------------------------------------------------------ 1. real-path rollback (no mocked accounting)


def _fail_after_real_movement(nth: int):
    """Wrap the REAL base-unit movement: it runs (the lot really changes in the
    transaction) and only afterwards does call number `nth` blow up."""
    real = InventoryService.apply_movement_base
    calls = {"n": 0}

    def wrapper(self, *args, **kwargs):
        movement = real(self, *args, **kwargs)
        calls["n"] += 1
        if calls["n"] == nth:
            raise RuntimeError("boom after the real movement")
        return movement

    return patch.object(InventoryService, "apply_movement_base", wrapper)


@pytest.mark.parametrize("op", ["correct", "remove", "move"])
def test_a_failure_after_a_real_base_movement_rolls_everything_back(db_session, op) -> None:
    env = Env(db_session, [("KG", "1"), ("G", "250")])
    env.receive("3", "KG", variant=0)
    env.receive("2", "KG", variant=0)  # a second lot (second batch)
    before = (_books(env), db_session.query(StockMovement).count(), db_session.query(AdminActionLog).count())
    with _fail_after_real_movement(2), pytest.raises(RuntimeError):
        if op == "correct":
            env.stock.correct_stock(env.product.id, ProductCorrectStockRequest(
                physical_amount=D("1"), amount_unit="KG", reason="count"), env.admin.id)  # needs both lots
        elif op == "remove":
            env.stock.remove_stock(env.product.id, ProductRemoveStockRequest(
                amount=D("4"), amount_unit="KG", reason="Damaged"), env.admin.id)
        else:
            env.stock.move_stock(env.product.id, ProductMoveStockRequest(
                amount=D("1.5"), amount_unit="KG", from_location_id=env.loc, to_location_id=env.loc2), env.admin.id)
    db_session.rollback()  # what the request layer does with an unhandled error
    db_session.expire_all()
    assert (_books(env), db_session.query(StockMovement).count(), db_session.query(AdminActionLog).count()) == before
    env.check_books()


# ------------------------------------------------------------------ 2/7/9. lifecycles per dimension, exact


def test_mass_lifecycle_3kg_sell_cancel_fulfil(db_session) -> None:
    env = Env(db_session, [("KG", "3"), ("G", "250")])
    env.receive("3", "KG")
    sold = env.order(1, "1")  # stays reserved
    cancelled = env.order(1, "1")
    fulfilled = env.order(1, "1")
    assert env.reserved() == 750
    env.release(cancelled)
    assert env.reserved() == 500
    env.consume(fulfilled)
    assert (env.physical(), env.reserved()) == (2750, 250)  # 3000 - 250 delivered; 250 g still held for `sold`
    env.consume(sold)
    assert (env.physical(), env.reserved()) == (2500, 0)
    env.check_books()


def test_volume_lifecycle_3l_sell_cancel_fulfil(db_session) -> None:
    env = Env(db_session, [("L", "3"), ("ML", "250"), ("L", "1")])
    env.receive("3", "L")
    held = env.order(1, "1")
    cancelled = env.order(1, "2")
    delivered = env.order(1, "1")
    assert env.reserved() == 1000
    env.release(cancelled)
    env.consume(delivered)
    assert (env.physical(), env.reserved()) == (2750, 250)  # ml, exactly
    env.release(held)
    assert (env.physical(), env.reserved()) == (2750, 0)
    assert env.packs() == [0, 11, 2]
    env.check_books()


def test_count_lifecycle_12_pieces_one_piece_consumption(db_session) -> None:
    env = Env(db_session, [("DOZEN", "1"), ("UNIT", "1")])
    env.receive("12", "UNIT")
    assert env.physical() == 12 and env.packs() == [1, 12]
    one = env.order(1, "1")
    env.consume(one)  # internal one-piece consumption
    assert env.physical() == 11 and env.packs() == [0, 11]
    env.stock.remove_stock(env.product.id, ProductRemoveStockRequest(
        amount=D("1"), amount_unit="UNIT", reason="sample"), env.admin.id)
    assert env.physical() == 10
    env.check_books()


def test_dozen_only_product_never_sells_a_single_piece(db_session) -> None:
    env = Env(db_session, [("DOZEN", "1")])
    env.receive("5", "UNIT")  # 5 loose pieces on the shelf
    assert env.physical() == 5 and env.packs() == [0]  # nothing a customer can buy
    with pytest.raises(ConflictError):
        env.order(0, "1")  # a dozen needs 12 pieces
    env.receive("7", "UNIT")
    assert env.packs() == [1]
    env.consume(env.order(0, "1"))
    assert env.physical() == 0  # exactly 12 pieces left the shelf


@pytest.mark.parametrize("specs, received, size_index, expected_left", [
    ([("KG", "3"), ("G", "250")], ("3", "KG"), 1, 2750),
    ([("DOZEN", "1"), ("UNIT", "1")], ("12", "UNIT"), 1, 11),
    ([("L", "3"), ("ML", "250")], ("3", "L"), 1, 2750),
])
def test_fulfilment_consumes_exactly_what_was_reserved(db_session, specs, received, size_index, expected_left) -> None:
    env = Env(db_session, specs)
    env.receive(*received)
    order = env.order(size_index, "1")
    assert env.reserved() == env.variants[size_index].size_base  # never 252 g / 1.008 pc
    env.consume(order)
    assert (env.physical(), env.reserved()) == (expected_left, 0)  # never 2748 / 10.992


# ------------------------------------------------------------------ 8. shared pool is not additive physical stock


def test_four_sizes_one_pool_are_views_not_additive_stock(db_session) -> None:
    env = Env(db_session, [("G", "250"), ("G", "500"), ("KG", "1"), ("KG", "3")])
    env.receive("1", "KG", variant=2)
    assert env.packs() == [4, 2, 1, 0]
    assert env.physical() == 1000 and env.pool() == 1000  # not 7 packs
    # size-specific stock on top of the shared pool: counted once
    env.inv.set_stock_shares(env.product.id, SetStockSharesRequest(
        shares=[{"variant_id": env.variants[2].id, "amount": D("500"), "amount_unit": "G"}], add=False), env.admin.id)
    pool, _, shares = pool_base_amounts(db_session, {env.product.id})
    assert pool[(env.product.id, "MASS")] == 500 and shares[env.variants[2].id] == 500
    assert env.packs() == [2, 1, 1, 0]  # shared 500 g; only the 1 kg size also sells its own 500 g
    assert env.physical() == 1000 and env.pool() == 1000
    env.check_books()
    # ordering the 1 kg pack uses the share first, then the pool: still 1000 g physical
    env.consume(env.order(2, "1"))
    assert env.physical() == 0
    env.check_books()


# ------------------------------------------------------------------ 6. quarantine, resolve, authorization


def _quarantine(db_session, lot: InventoryLot) -> None:
    db_session.execute(text("UPDATE inventory_lots SET quantity_base = NULL, reserved_base = NULL WHERE id = :i"), {"i": lot.id})
    db_session.commit()


def test_quarantined_lot_never_takes_part_in_sellable_stock(db_session) -> None:
    env = Env(db_session, [("DOZEN", "1"), ("UNIT", "1")])
    good = env.receive("12", "UNIT")
    held = env.receive("1", "DOZEN", location=env.loc2)
    _quarantine(db_session, held)
    assert env.pool() == 12 and env.packs() == [1, 12]  # only the trusted lot counts
    env.consume(env.order(1, "12"))  # allocation never touches the held lot
    db_session.expire_all()
    assert db_session.get(InventoryLot, good.id).quantity_base == 0
    assert db_session.get(InventoryLot, held.id).quantity_base is None
    with pytest.raises(ConflictError):
        env.order(1, "1")  # the held lot does not make stock appear


def test_resolve_changes_inventory_exactly_once_and_is_idempotent(client, db_session) -> None:
    env = Env(db_session, [("DOZEN", "1"), ("UNIT", "1")])
    held = env.receive("1", "DOZEN")
    _quarantine(db_session, held)
    _staff_user, headers = _staff(db_session, HUB_STAFF, "resolve")
    url = f"{API}/admin/lots/{held.id}/resolve-base"
    first = client.post(url, json={"quantity_base": 5, "reason": "recounted: 5 pieces"}, headers=headers)
    assert first.status_code == 204, first.text
    assert env.pool() == 5 and env.packs() == [0, 5]
    again = client.post(url, json={"quantity_base": 5, "reason": "recounted: 5 pieces"}, headers=headers)
    assert again.status_code == 422  # no longer on hold: nothing is applied twice
    assert env.pool() == 5
    db_session.expire_all()
    audits = db_session.query(AdminActionLog).filter(AdminActionLog.action == "inventory.resolve_lot").count()
    assert audits == 1


def test_only_staff_with_the_stock_permission_can_resolve_a_lot(client, db_session) -> None:
    env = Env(db_session, [("DOZEN", "1")])
    held = env.receive("1", "DOZEN")
    _quarantine(db_session, held)
    _c, customer_headers = _staff(db_session, CUSTOMER, "resolve_c")
    url = f"{API}/admin/lots/{held.id}/resolve-base"
    body = {"quantity_base": 5, "reason": "nope nope"}
    assert client.post(url, json=body).status_code in (401, 403)
    assert client.post(url, json=body, headers=customer_headers).status_code == 403
    db_session.expire_all()
    assert db_session.get(InventoryLot, held.id).quantity_base is None  # untouched


def test_resolving_below_the_reserved_amount_is_refused(db_session) -> None:
    env = Env(db_session, [("KG", "3"), ("G", "250")])
    lot = env.receive("3", "KG")
    env.order(1, "2")  # 500 g reserved against the lot
    db_session.execute(text("UPDATE inventory_lots SET quantity_base = NULL, reserved_base = NULL WHERE id = :i"), {"i": lot.id})
    db_session.commit()
    with pytest.raises(BusinessValidationError):
        env.inv.resolve_lot_base(lot.id, 400, "too low to cover the order", env.admin.id)
    env.inv.resolve_lot_base(lot.id, 3000, "confirmed", env.admin.id)
    db_session.expire_all()
    fixed = db_session.get(InventoryLot, lot.id)
    assert (fixed.quantity_base, fixed.reserved_base) == (3000, 500)  # the live order's 500 g is carried over


# ------------------------------------------------------------------ 5. API compatibility


def test_admin_lot_responses_carry_exact_integers_and_old_pack_fields(client, db_session) -> None:
    env = Env(db_session, [("KG", "3"), ("G", "250")])
    lot = env.receive("3", "KG")
    env.order(1, "1")
    _u, headers = _staff(db_session, HUB_STAFF, "api")
    body = client.get(f"{API}/admin/lots/{lot.id}", headers=headers).json()
    assert body["on_hand_base"] == 3000 and body["reserved_base"] == 250 and body["size_base"] == 3000
    assert isinstance(body["on_hand_base"], int) and isinstance(body["reserved_base"], int)
    assert body["on_hand"] == "1.000" and body["reserved"] == "0.083"  # legacy pack display fields are still there
    listing = client.get(f"{API}/admin/lots", headers=headers).json()["items"]
    mine = next(i for i in listing if i["id"] == lot.id)
    assert mine["on_hand_base"] == 3000 and isinstance(mine["reserved_base"], int)


def test_old_pack_quantities_cannot_overwrite_authoritative_stock(client, db_session) -> None:
    env = Env(db_session, [("KG", "3"), ("G", "250")])
    lot = env.receive("3", "KG")
    env.order(1, "1")  # 250 g reserved: base 3000 / 250
    _u, headers = _staff(db_session, HUB_STAFF, "api2")
    # there is no endpoint that SETS a lot's pack quantity; every pack input is a movement that must be exact
    assert client.patch(f"{API}/admin/lots/{lot.id}", json={"quantity": "9.000"}, headers=headers).status_code in (404, 405)
    assert client.put(f"{API}/admin/lots/{lot.id}", json={"quantity": "9.000"}, headers=headers).status_code in (404, 405)
    # a legacy pack count that is not a whole number of grams is refused, never rounded
    odd = client.post(f"{API}/lots/{lot.id}/movements",
                      json={"movement_type": "ADJUSTMENT_OUT", "quantity": "0.0007"}, headers=headers)
    assert odd.status_code == 422, odd.text
    # a legitimate legacy pack movement is applied exactly in base units
    ok = client.post(f"{API}/lots/{lot.id}/movements",
                     json={"movement_type": "ADJUSTMENT_OUT", "quantity": "0.5"}, headers=headers)
    assert ok.status_code in (200, 201), ok.text
    db_session.expire_all()
    fresh = db_session.get(InventoryLot, lot.id)
    assert (fresh.quantity_base, fresh.reserved_base) == (1500, 250)
    reconcile = client.post(f"{API}/admin/lots/{lot.id}/reconcile",
                            json={"physical_count": "0.5", "reason": "count"}, headers=headers)
    assert reconcile.status_code == 200, reconcile.text
    db_session.expire_all()
    assert db_session.get(InventoryLot, lot.id).quantity_base == 1500  # 0.5 pack of 3 kg: exact


def test_creating_a_lot_with_an_inexact_pack_quantity_is_a_clean_422(client, db_session) -> None:
    env = Env(db_session, [("DOZEN", "1")])
    lot = env.receive("1", "DOZEN")
    batch_id, variant_id, location_id = lot.batch_id, lot.variant_id, env.loc2
    _u, headers = _staff(db_session, HUB_STAFF, "api3")
    response = client.post(f"{API}/lots", json={"batch_id": batch_id, "variant_id": variant_id,
                                               "location_id": location_id, "quantity": "0.416"}, headers=headers)
    assert response.status_code == 422, response.text  # 4.992 pieces: refused, not rounded
    assert db_session.query(func.count(InventoryLot.id)).filter(InventoryLot.location_id == location_id).scalar() == 0


def test_a_warehouse_holding_one_gram_cannot_be_deleted(client, db_session) -> None:
    env = Env(db_session, [("KG", "3")])
    env.receive("1", "G")  # 1 g of a 3 kg size: the legacy pack column rounds to 0.000
    db_session.expire_all()
    assert db_session.query(InventoryLot).filter(InventoryLot.location_id == env.loc).one().quantity == D("0.000")
    _u, headers = _staff(db_session, "ADMIN", "api4")
    response = client.delete(f"{API}/locations/{env.loc}", headers=headers)
    assert response.status_code == 409, response.text


# ------------------------------------------------------------------ 10. no float on the authoritative path


_AUTHORITATIVE = ["services/units.py", "services/stock_pool.py", "services/inventory.py",
                  "services/inventory_reservation.py", "services/product_stock.py", "services/fulfillment.py"]


@pytest.mark.parametrize("path", _AUTHORITATIVE)
def test_no_float_arithmetic_on_authoritative_stock_code(path) -> None:
    source = (APP / path).read_text(encoding="utf-8")
    assert not re.search(r"\bfloat\s*\(|\bround\s*\(|math\.(floor|ceil)", source), path


# ------------------------------------------------------------------ 3. no legacy write path may come back


def test_only_the_base_unit_layer_and_quarantine_branches_write_lot_quantities() -> None:
    allowed = {
        # (file, pattern) pairs that are intentional
        ("services/inventory_reservation.py", r"lot\.reserved_quantity = "),  # quarantined (NULL-base) lots only
        ("services/inventory_reservation.py", r"lot\.quantity = "),
    }
    offenders = []
    for path in APP.rglob("*.py"):
        if "models" in path.parts or "alembic" in path.parts:
            continue
        rel = path.relative_to(APP).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.search(r"\b(lot|share_lot|back|dest|src|target|source|output_lot)\.(quantity|reserved_quantity)\s*(-|\+)?=\s", stripped):
                if not any(rel == f and re.search(p, stripped) for f, p in allowed):
                    offenders.append(f"{rel}:{number}: {stripped}")
    assert offenders == [], offenders
    sql = [str(p) for p in APP.rglob("*.py") if re.search(r"UPDATE\s+inventory_lots|insert\(InventoryLot", p.read_text(encoding="utf-8"), re.I)]
    assert sql == []


def test_base_columns_are_written_only_in_the_accounting_layer() -> None:
    expected = {
        "services/inventory.py": 2,  # apply_movement_base, resolve_lot_base (3 assignments across 2 functions)
        "services/inventory_reservation.py": 3,  # reserve, release, consume
    }
    found: dict[str, int] = {}
    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP).as_posix()
        if rel.startswith("models/"):
            continue
        hits = [
            line for line in path.read_text(encoding="utf-8").splitlines()
            if re.search(r"\.(quantity_base|reserved_base)\s*(-|\+)?=\s", line) and not line.strip().startswith("#")
        ]
        if hits:
            found[rel] = len(hits)
    assert set(found) == set(expected), found
    assert found["services/inventory_reservation.py"] == 3 and found["services/inventory.py"] == 3, found


# ------------------------------------------------------------------ CHECK constraints must not let NULL through


def test_a_null_base_cannot_smuggle_a_zero_or_negative_quantity_past_the_checks(db_session) -> None:
    from sqlalchemy.exc import IntegrityError

    env = Env(db_session, [("KG", "1")])
    lot = env.receive("1", "KG")
    for bad in (D("0"), D("-1")):
        db_session.add(StockMovement(
            inventory_lot_id=lot.id, movement_type="ADJUSTMENT_IN", quantity=bad, quantity_base=None,
            performed_by_user_id=env.admin.id, occurred_at=datetime.now(UTC)))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
    defs = {
        row[0]: row[1] for row in db_session.execute(text(
            "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname IN ('ck_stock_movements_quantity', 'ck_inventory_reservation_items_quantity')")).fetchall()
    }
    assert len(defs) == 2 and all("COALESCE" in d for d in defs.values()), defs


def test_an_invalid_variant_size_is_refused_by_the_database_not_silently_accepted(db_session) -> None:
    from sqlalchemy.exc import IntegrityError

    from app.models.product_variant import ProductVariant

    env = Env(db_session, [("KG", "1")])
    for unit, qty in (("OUNCE", "1"), ("KG", "0")):
        db_session.add(ProductVariant(product_id=env.product.id, name="bad", sku=f"BAD-{unit}-{qty}", unit=unit,
                                      quantity=D(qty), status="ACTIVE"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
    with pytest.raises(BusinessValidationError):  # a real unit with a half-gram size: a clear 422, not a DB error
        db_session.add(ProductVariant(product_id=env.product.id, name="half g", sku="HALF-G", unit="KG",
                                      quantity=D("0.0005"), status="ACTIVE"))
        db_session.commit()
    db_session.rollback()
