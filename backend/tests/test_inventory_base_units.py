"""Inventory is accounted in EXACT integer base units (g / ml / pieces).

Real PostgreSQL. Every assertion is in base units: unit conversion alone must
never create or destroy stock, whatever size the stock was received as or sold in.
"""

import random
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal as D
from types import SimpleNamespace

import pytest
from sqlalchemy import func, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.exceptions.base import BusinessValidationError, ConflictError
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.schemas.admin_inventory import (
    ProductCorrectStockRequest,
    ProductMoveStockRequest,
    ProductRemoveStockRequest,
    ReceiveStockRequest,
    SetStockSharesRequest,
)
from app.services import units as U
from app.services.checkout_session import CheckoutSessionService
from app.services.inventory import InventoryService
from app.services.inventory_reservation import (
    InventoryReservationService,
    consume_reserved,
)
from app.services.product_stock import ProductStockService
from app.services.stock_pool import available_packs_by_variant, pool_base_amounts
from tests.test_phase_15_inventory_reservation_fulfillment import (
    _create_product_variant,
    _create_user_with_role,
)

NOW = datetime.now(UTC)


class Env:
    """One product with the given sizes, two warehouses, an admin and a customer."""

    def __init__(self, db: Session, specs: list[tuple[str, str]]) -> None:
        self.db = db
        tag = uuid.uuid4().hex[:8].upper()
        product, first = _create_product_variant(db, tag=tag)
        first.unit, first.quantity, first.name = specs[0][0], D(specs[0][1]), f"{specs[0][1]} {specs[0][0]}"
        db.commit()
        self.product: Product = product
        self.variants: list[ProductVariant] = [first]
        for unit, qty in specs[1:]:
            v = ProductVariant(
                product_id=product.id, name=f"{qty} {unit}", sku=f"SKU-{tag}-{qty}{unit}",
                unit=unit, quantity=D(qty), status="ACTIVE",
            )
            db.add(v)
            db.commit()
            db.refresh(v)
            self.variants.append(v)
        self.admin = _create_user_with_role(db, "ADMIN", f"adm{tag}@example.com")
        self.customer = _create_user_with_role(db, "CUSTOMER", f"cus{tag}@example.com")
        self.loc = self._location(f"{tag}-A")
        self.loc2 = self._location(f"{tag}-B")
        self.dimension = U.dimension_of(first.unit)
        self.inv = InventoryService(db)
        self.res = InventoryReservationService(db)
        self.stock = ProductStockService(db)

    def _location(self, code: str) -> int:
        loc = InventoryLocation(name=f"Hub-{code}", code=f"H-{code}", type="WAREHOUSE", address_line_1="1 Rd",
                                city="Nagpur", state="MH", postal_code="440001", status="ACTIVE")
        self.db.add(loc)
        self.db.commit()
        return loc.id

    # ---- actions ----
    def receive(self, amount: str, unit: str, *, variant: int = 0, location: int | None = None) -> InventoryLot:
        lot = self.inv.receive_stock(
            ReceiveStockRequest(variant_id=self.variants[variant].id, location_id=location or self.loc,
                                amount=D(amount), amount_unit=unit),
            self.admin.id,
        )
        self.db.expire_all()
        return self.db.get(InventoryLot, lot.id)

    def order(self, variant: int, packs: str = "1") -> Order:
        v = self.variants[variant]
        order = Order(user_id=self.customer.id, order_number=f"T{uuid.uuid4().hex[:14]}", status="PENDING",
                      total_amount=D("1"), subtotal_amount=D("1"), currency="INR", placed_at=NOW)
        self.db.add(order)
        self.db.flush()
        item = OrderItem(order_id=order.id, variant_id=v.id, product_name=self.product.name, variant_name=v.name,
                         sku=v.sku, unit=v.unit, quantity=D(packs), unit_price=D("1"), total_price=D("1"))
        self.db.add(item)
        self.db.flush()
        self.res.create_reservation_for_order(order, [item])
        self.db.commit()
        return order

    def release(self, order: Order) -> None:
        self.res.release_reservation_for_order(order.id, now=NOW, reason="test")
        self.db.commit()

    def consume(self, order: Order) -> None:
        from app.models.inventory_reservation import InventoryReservation
        from app.models.inventory_reservation_item import InventoryReservationItem

        reservation = self.db.query(InventoryReservation).filter_by(order_id=order.id).one()
        for item in self.db.query(InventoryReservationItem).filter_by(reservation_id=reservation.id).all():
            lot = self.db.query(InventoryLot).filter_by(id=item.inventory_lot_id).with_for_update().one()
            consume_reserved(self.inv, lot, item, self.admin.id, order.id, "test_delivery")
        self.db.commit()

    # ---- observations (all exact integers) ----
    def lots(self) -> list[InventoryLot]:
        self.db.expire_all()
        ids = [v.id for v in self.variants]
        return self.db.query(InventoryLot).filter(InventoryLot.variant_id.in_(ids)).order_by(InventoryLot.id).all()

    def physical(self) -> int:
        return sum(lot.quantity_base for lot in self.lots())

    def reserved(self) -> int:
        return sum(lot.reserved_base for lot in self.lots())

    def pool(self) -> int:
        self.db.expire_all()
        pool, _, shares = pool_base_amounts(self.db, {self.product.id})
        return pool[(self.product.id, self.dimension)] + sum(shares.values())

    def packs(self) -> list[int]:
        self.db.expire_all()
        got = available_packs_by_variant(self.db, [v.id for v in self.variants])
        return [int(got[v.id]) for v in self.variants]

    def check_books(self) -> None:
        """The conservation identity the whole system must hold at all times."""
        physical, reserved = self.physical(), self.reserved()
        assert 0 <= reserved <= physical
        assert self.pool() == physical - reserved  # nothing counted twice, nothing lost
        for lot in self.lots():
            assert 0 <= lot.reserved_base <= lot.quantity_base


MASS = [("KG", "3"), ("G", "250"), ("G", "500"), ("KG", "1")]
VOLUME = [("L", "5"), ("ML", "250"), ("ML", "500"), ("L", "1")]
COUNT = [("DOZEN", "1"), ("UNIT", "1"), ("UNIT", "6"), ("UNIT", "12")]


# ------------------------------------------------------------------ the brief's cases


def test_case_a_250g_from_a_3kg_lot_reserves_exactly_250g(db_session) -> None:
    env = Env(db_session, [("KG", "3"), ("G", "250")])
    lot = env.receive("3", "KG")
    assert lot.quantity_base == 3000
    order = env.order(1, "1")
    lot = env.lots()[0]
    assert lot.reserved_base == 250 and lot.quantity_base - lot.reserved_base == 2750  # never 252
    env.consume(order)
    lot = env.lots()[0]
    assert (lot.quantity_base, lot.reserved_base) == (2750, 0)
    env.check_books()


def test_case_b_one_piece_taken_from_a_dozen_lot_leaves_exactly_eleven(db_session) -> None:
    env = Env(db_session, [("DOZEN", "1"), ("UNIT", "1")])
    env.receive("1", "DOZEN")
    assert env.physical() == 12
    result = env.stock.remove_stock(
        env.product.id, ProductRemoveStockRequest(amount=D("1"), amount_unit="UNIT", reason="sample"), env.admin.id
    )
    assert result.product is not None
    assert env.physical() == 11  # never 10.992 / 1.008 pieces
    env.check_books()


def test_case_c_five_pieces_received_against_the_dozen_size_are_exactly_five(db_session) -> None:
    env = Env(db_session, [("DOZEN", "1"), ("UNIT", "1")])
    lot = env.receive("5", "UNIT", variant=0)  # the UI picked the dozen size
    assert lot.quantity_base == 5
    assert env.packs() == [0, 5]  # no dozen yet, five single pieces
    env.check_books()


def test_case_d_68999_grams_shared_pool(db_session) -> None:
    env = Env(db_session, [("G", "250"), ("KG", "1")])
    env.receive("68.999", "KG", variant=1)
    assert env.pool() == 68999
    assert env.packs() == [275, 68]


def test_case_e_a_shared_pool_is_not_added_up_per_size(db_session) -> None:
    env = Env(db_session, [("G", "250"), ("G", "500"), ("KG", "1")])
    env.receive("1", "KG", variant=2)
    assert env.packs() == [4, 2, 1]
    assert env.physical() == 1000 and env.pool() == 1000  # not 4+2+1 packs of anything


def test_dozen_only_product_cannot_sell_pieces_but_counts_pieces(db_session) -> None:
    env = Env(db_session, [("DOZEN", "1")])
    env.receive("1", "DOZEN")
    assert env.physical() == 12 and env.packs() == [1]
    env.receive("5", "UNIT")
    assert env.physical() == 17 and env.packs() == [1]  # 17 pieces = 1 whole dozen on sale


# ------------------------------------------------------------------ the full matrix


MASS_AMOUNTS = [1, 5, 10, 50, 100, 250, 500, 750, 1000, 1500, 3000, 5000]
SIZES = {
    "MASS": [("G", "1"), ("G", "10"), ("G", "50"), ("G", "100"), ("G", "250"), ("G", "500"), ("KG", "1"), ("KG", "1.5"), ("KG", "3"), ("KG", "5")],
    "VOLUME": [("ML", "10"), ("ML", "50"), ("ML", "100"), ("ML", "250"), ("ML", "500"), ("L", "1"), ("L", "1.5"), ("L", "3"), ("L", "5")],
    "COUNT": [("UNIT", "1"), ("UNIT", "2"), ("UNIT", "6"), ("UNIT", "12"), ("DOZEN", "1"), ("DOZEN", "2"), ("DOZEN", "3")],
}
BASE_UNIT = {"MASS": "G", "VOLUME": "ML", "COUNT": "UNIT"}
AMOUNTS = {
    "MASS": MASS_AMOUNTS,
    "VOLUME": MASS_AMOUNTS,
    "COUNT": [1, 2, 5, 6, 10, 12, 24, 36, 100],
}


@pytest.mark.parametrize("dimension", ["MASS", "VOLUME", "COUNT"])
@pytest.mark.parametrize("received_via", [0, -1])  # received against the smallest / the largest size
def test_matrix_receive_reserve_release_consume_conserve_stock(db_session, dimension, received_via) -> None:
    env = Env(db_session, SIZES[dimension])
    sizes = [v.size_base for v in env.variants]
    expected_physical = 0
    for amount in AMOUNTS[dimension]:
        env.receive(str(amount), BASE_UNIT[dimension], variant=received_via)
        expected_physical += amount
        assert env.physical() == expected_physical  # received == stored, whatever the size
        env.check_books()
    assert env.packs() == [expected_physical // s for s in sizes]

    # reserve -> release restores exactly; reserve -> consume removes exactly the pack
    for index, size in enumerate(sizes):
        if env.packs()[index] < 1:
            continue
        before = (env.physical(), env.reserved())
        order = env.order(index, "1")
        assert env.reserved() == before[1] + size  # exactly one pack, never a rounded neighbour
        env.check_books()
        env.release(order)
        assert (env.physical(), env.reserved()) == before  # cancel/restore: exact
        order = env.order(index, "1")
        env.consume(order)
        assert env.physical() == before[0] - size and env.reserved() == before[1]
        expected_physical -= size
        env.check_books()
    assert env.physical() == expected_physical


@pytest.mark.parametrize(
    "specs, size_index, packs",
    [
        ([("KG", "3"), ("G", "250")], 1, "4"),
        ([("KG", "3"), ("KG", "1.5")], 1, "1"),
        ([("DOZEN", "1"), ("UNIT", "1")], 1, "7"),
        ([("DOZEN", "1"), ("UNIT", "6")], 1, "2"),
        ([("L", "3"), ("ML", "250")], 1, "5"),
        ([("L", "5"), ("L", "1.5")], 1, "2"),
    ],
)
def test_awkward_lot_sizes_reserve_exactly_what_was_ordered(db_session, specs, size_index, packs) -> None:
    env = Env(db_session, specs)
    big = env.variants[0]
    env.receive(str(big.quantity), big.unit)  # one pack of the big size
    order = env.order(size_index, packs)
    wanted = env.variants[size_index].size_base * int(packs)
    assert env.reserved() == wanted
    env.release(order)
    assert env.reserved() == 0 and env.physical() == big.size_base


@pytest.mark.parametrize("amount, unit, packs", [("250", "G", "1"), ("1", "UNIT", "1"), ("5", "UNIT", "1"),
                                                  ("1", "DOZEN", "1"), ("250", "ML", "1"), ("1", "L", "1")])
def test_one_hundred_reserve_release_cycles_never_drift(db_session, amount, unit, packs) -> None:
    dimension = U.dimension_of(unit)
    specs = {"MASS": [("KG", "3"), ("G", "250")], "VOLUME": [("L", "3"), ("ML", "250"), ("L", "1")],
             "COUNT": [("DOZEN", "1"), ("UNIT", "1"), ("UNIT", "5")]}[dimension]
    env = Env(db_session, specs)
    big = env.variants[0]
    env.receive(str(big.quantity), big.unit)
    index = next(i for i, v in enumerate(env.variants) if v.size_base == U.to_base(D(amount), unit))
    start = (env.physical(), env.reserved())
    for _ in range(100):
        env.release(env.order(index, packs))
    assert (env.physical(), env.reserved()) == start


# ------------------------------------------------------------------ conservation (random walks)


@pytest.mark.parametrize("seed", [1, 7, 42])
@pytest.mark.parametrize("specs", [MASS, VOLUME, COUNT])
def test_random_operation_sequences_conserve_stock(db_session, seed, specs) -> None:
    rng = random.Random(seed)
    env = Env(db_session, specs)
    base_unit = BASE_UNIT[env.dimension]
    expected = 0
    open_orders: list[Order] = []
    for _ in range(35):
        op = rng.choice(["receive", "receive", "reserve", "reserve", "release", "consume", "remove", "correct", "move", "share"])
        if op == "receive":
            amount = rng.choice([1, 3, 5, 12, 100, 250, 750, 1000, 3000])
            env.receive(str(amount), base_unit, variant=rng.randrange(len(env.variants)),
                        location=rng.choice([env.loc, env.loc2]))
            expected += amount
        elif op == "reserve":
            index = rng.randrange(len(env.variants))
            if env.packs()[index] >= 1:
                open_orders.append(env.order(index, "1"))
        elif op == "release" and open_orders:
            env.release(open_orders.pop(rng.randrange(len(open_orders))))
        elif op == "consume" and open_orders:
            order = open_orders.pop(rng.randrange(len(open_orders)))
            wanted = sum(
                i.quantity_base for i in env.db.query(__import__("app.models.inventory_reservation_item", fromlist=["x"]).InventoryReservationItem).all()
                if i.reservation.order_id == order.id
            )
            env.consume(order)
            expected -= wanted
        elif op == "remove":
            free = env.pool()
            take = min(free, rng.choice([1, 2, 5, 50]))
            if take > 0:
                env.stock.remove_stock(env.product.id, ProductRemoveStockRequest(
                    amount=D(take), amount_unit=base_unit, reason="spoiled"), env.admin.id)
                expected -= take
        elif op == "correct":
            counted = max(env.physical() + rng.choice([-3, 0, 4, 100]), env.reserved())
            try:
                env.stock.correct_stock(env.product.id, ProductCorrectStockRequest(
                    physical_amount=D(counted), amount_unit=base_unit, location_id=None, reason="count"), env.admin.id)
                expected = counted if len({lot.location_id for lot in env.lots()}) <= 1 else expected
            except BusinessValidationError:
                env.db.rollback()
        elif op == "move":
            free = env.pool()
            take = min(free, rng.choice([1, 5, 50]))
            if take > 0:
                try:
                    env.stock.move_stock(env.product.id, ProductMoveStockRequest(
                        amount=D(take), amount_unit=base_unit, from_location_id=env.loc, to_location_id=env.loc2), env.admin.id)
                except (BusinessValidationError, ConflictError):
                    env.db.rollback()
        elif op == "share":
            free = env.pool()
            take = min(free, rng.choice([5, 250, 1000]))
            if take > 0:
                try:
                    env.inv.set_stock_shares(env.product.id, SetStockSharesRequest(
                        shares=[{"variant_id": env.variants[rng.randrange(len(env.variants))].id,
                                 "amount": D(take), "amount_unit": base_unit}], add=True), env.admin.id)
                except (BusinessValidationError, ConflictError):
                    env.db.rollback()
        env.check_books()
        # movements are an exact ledger of physical stock
        env.db.expire_all()
        moved = env.db.execute(text(
            "SELECT COALESCE(SUM(CASE WHEN m.movement_type IN ('RECEIPT','ADJUSTMENT_IN','TRANSFER_IN') THEN m.quantity_base "
            "ELSE -m.quantity_base END), 0) FROM stock_movements m JOIN inventory_lots l ON l.id = m.inventory_lot_id "
            "WHERE l.variant_id = ANY(:ids)"), {"ids": [v.id for v in env.variants]}).scalar()
        assert int(moved) == env.physical()
    for order in open_orders:
        env.release(order)
    env.check_books()
    assert env.reserved() == 0


# ------------------------------------------------------------------ shares (size-specific stock)


def test_size_specific_stock_is_not_double_counted(db_session) -> None:
    env = Env(db_session, [("G", "250"), ("KG", "1")])
    env.receive("2", "KG", variant=1)
    env.inv.set_stock_shares(env.product.id, SetStockSharesRequest(
        shares=[{"variant_id": env.variants[1].id, "amount": D("500"), "amount_unit": "G"}], add=False), env.admin.id)
    pool, _, shares = pool_base_amounts(db_session, {env.product.id})
    assert pool[(env.product.id, "MASS")] == 1500 and shares[env.variants[1].id] == 500
    assert env.packs() == [6, 2]  # 250 g sells from the shared 1500 g; 1 kg from 1500 + its own 500
    assert env.physical() == 2000
    env.check_books()
    # the share belongs to the 1 kg size only: 7 x 250 g is not possible
    with pytest.raises(ConflictError):
        env.order(0, "7")


# ------------------------------------------------------------------ checkout / availability


def test_checkout_precheck_uses_the_shared_pool(db_session) -> None:
    env = Env(db_session, [("KG", "3"), ("G", "250")])
    env.receive("3", "KG", variant=0)
    service = object.__new__(CheckoutSessionService)
    service.db = db_session
    plan = SimpleNamespace(cart_items=[(env.variants[1].id, D("12"))], order_item_rows=[])
    service._require_stock(plan)  # 12 x 250 g == 3 kg: fine, it is in a 3 kg lot
    too_much = SimpleNamespace(cart_items=[(env.variants[1].id, D("13"))],
                               order_item_rows=[{"variant_id": env.variants[1].id, "product_name": "x", "variant_name": "y"}])
    with pytest.raises(ConflictError):
        service._require_stock(too_much)


def test_two_orders_can_never_reserve_more_than_exists(db_session) -> None:
    env = Env(db_session, [("KG", "1"), ("G", "250")])
    env.receive("1", "KG")
    variant_id, user_id = env.variants[1].id, env.customer.id
    product_name = env.product.name

    def attempt(_: int) -> str:
        db = SessionLocal()
        try:
            order = Order(user_id=user_id, order_number=f"C{uuid.uuid4().hex[:14]}", status="PENDING",
                          total_amount=D("1"), subtotal_amount=D("1"), currency="INR", placed_at=NOW)
            db.add(order)
            db.flush()
            item = OrderItem(order_id=order.id, variant_id=variant_id, product_name=product_name, variant_name="250 G",
                             sku="s", unit="G", quantity=D("2"), unit_price=D("1"), total_price=D("1"))
            db.add(item)
            db.flush()
            InventoryReservationService(db).create_reservation_for_order(order, [item])
            db.commit()
            return "ok"
        except ConflictError:
            db.rollback()
            return "refused"
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))
    assert results.count("ok") == 2 and results.count("refused") == 4  # 1000 g / 500 g each
    env.check_books()
    assert env.reserved() == 1000


# ------------------------------------------------------------------ dimensions are never mixed


@pytest.mark.parametrize("variant_unit, amount_unit", [("KG", "L"), ("G", "ML"), ("KG", "UNIT"), ("L", "DOZEN"), ("DOZEN", "G")])
def test_receiving_in_another_dimension_is_refused(db_session, variant_unit, amount_unit) -> None:
    env = Env(db_session, [(variant_unit, "1")])
    with pytest.raises(BusinessValidationError):
        env.receive("1", amount_unit)
    assert env.physical() == 0


def test_a_fractional_base_amount_is_refused_not_rounded(db_session) -> None:
    env = Env(db_session, [("KG", "1")])
    with pytest.raises(BusinessValidationError):
        env.receive("0.5", "G")  # half a gram
    assert env.physical() == 0


# ------------------------------------------------------------------ database guarantees


def test_trigger_keeps_legacy_pack_columns_and_base_in_step(db_session) -> None:
    env = Env(db_session, [("KG", "3")])
    lot = env.receive("3", "KG")
    assert (lot.quantity, lot.quantity_base) == (D("1.000"), 3000)
    lot.reserved_base = 250
    db_session.commit()
    db_session.refresh(lot)
    assert lot.reserved_quantity == D("0.083") and lot.reserved_base == 250  # exact base, display packs
    lot.quantity = D("0.500")  # a legacy writer: packs in, exact base derived
    lot.reserved_quantity = D("0")
    db_session.commit()
    db_session.refresh(lot)
    assert (lot.quantity_base, lot.reserved_base) == (1500, 0)


def test_legacy_write_that_is_not_a_whole_number_of_base_units_is_rejected(db_session) -> None:
    env = Env(db_session, [("DOZEN", "1")])
    lot = env.receive("1", "DOZEN")
    lot.quantity = D("0.416")  # 4.992 pieces
    with pytest.raises(DBAPIError):
        db_session.commit()
    db_session.rollback()
    assert env.physical() == 12


def test_database_refuses_reserving_more_than_physical(db_session) -> None:
    env = Env(db_session, [("G", "250")])
    lot = env.receive("500", "G")
    lot.reserved_base = 501
    with pytest.raises(DBAPIError):
        db_session.commit()
    db_session.rollback()


def test_a_lot_on_hold_for_review_is_never_sold_or_moved(db_session) -> None:
    env = Env(db_session, [("DOZEN", "1"), ("UNIT", "1")])
    lot = env.receive("1", "DOZEN")
    db_session.execute(text("UPDATE inventory_lots SET quantity_base = NULL, reserved_base = NULL WHERE id = :i"), {"i": lot.id})
    db_session.commit()
    assert env.packs() == [0, 0]  # excluded from sellable stock
    db_session.expire_all()
    held = db_session.get(InventoryLot, lot.id)
    with pytest.raises(BusinessValidationError):
        env.inv.apply_movement_base(held, "ADJUSTMENT_OUT", 1, env.admin.id)
    with pytest.raises(ConflictError):
        env.order(1, "1")


def test_variant_size_base_follows_quantity_and_unit(db_session) -> None:
    env = Env(db_session, [("KG", "1.5"), ("DOZEN", "2")]) if False else Env(db_session, [("KG", "1.5")])
    assert env.variants[0].size_base == 1500
    env.variants[0].quantity = D("2")
    db_session.commit()
    assert db_session.get(ProductVariant, env.variants[0].id).size_base == 2000
    assert db_session.query(func.count(InventoryLot.id)).scalar() == 0


# ------------------------------------------------------------------ product-level reserve (one physical amount)


def test_product_reserve_is_one_physical_amount_for_every_size(db_session) -> None:
    from app.services.stock_alerts import list_stock_alerts
    from app.services.stock_levels import BELOW, OK, variant_stock_level

    # the pure rule: 5000 g is 20 x 250 g, 10 x 500 g, 5 x 1 kg - sizes agree
    for packs in (16, 8, 4):  # 4000 g expressed in each size
        assert variant_stock_level(packs, None, 4000, 5000) == BELOW
    assert variant_stock_level(40, None, 10000, 5000) == OK
    assert variant_stock_level(0, None, 4000, 5000) == "OUT"  # a size that cannot sell one pack

    env = Env(db_session, [("G", "250"), ("G", "500"), ("KG", "1")])
    env.receive("4", "KG", variant=2)
    for v in env.variants:  # the legacy per-size default (10 packs) would flag every size here
        db_session.refresh(v)
    env.inv.set_product_reserve(env.product.id, D("5"), "KG", env.admin.id)
    mine = {a.variant_id: a for a in list_stock_alerts(db_session) if a.product_id == env.product.id}
    assert {a.level for a in mine.values()} == {BELOW}
    assert mine[env.variants[0].id].reserve_level == 20  # 5000 g read as packs of 250 g
    assert mine[env.variants[2].id].reserve_level == 5
    env.receive("10", "KG", variant=2)  # 14 kg: comfortably above 5 kg
    assert [a for a in list_stock_alerts(db_session) if a.product_id == env.product.id] == []
    env.inv.set_product_reserve(env.product.id, None, None, env.admin.id)  # back to the per-size rule
    assert {a.level for a in list_stock_alerts(db_session) if a.product_id == env.product.id} <= {BELOW, "NEAR"}


def test_product_reserve_must_be_in_a_unit_the_product_has(db_session) -> None:
    env = Env(db_session, [("KG", "1")])
    with pytest.raises(BusinessValidationError):
        env.inv.set_product_reserve(env.product.id, D("5"), "L", env.admin.id)
    with pytest.raises(BusinessValidationError):
        env.inv.set_product_reserve(env.product.id, D("0.5"), "G", env.admin.id)  # half a gram


def test_admin_can_resolve_a_lot_that_was_held_for_review(db_session) -> None:
    env = Env(db_session, [("DOZEN", "1"), ("UNIT", "1")])
    lot = env.receive("1", "DOZEN")
    db_session.execute(text("UPDATE inventory_lots SET quantity_base = NULL, reserved_base = NULL WHERE id = :i"), {"i": lot.id})
    db_session.commit()
    assert env.packs() == [0, 0]
    env.inv.resolve_lot_base(lot.id, 5, "recounted by hand: 5 pieces", env.admin.id)
    db_session.expire_all()
    assert (db_session.get(InventoryLot, lot.id).quantity_base, db_session.get(InventoryLot, lot.id).reserved_base) == (5, 0)
    assert env.packs() == [0, 5]
    with pytest.raises(BusinessValidationError):
        env.inv.resolve_lot_base(lot.id, 6, "again", env.admin.id)  # no longer on hold
