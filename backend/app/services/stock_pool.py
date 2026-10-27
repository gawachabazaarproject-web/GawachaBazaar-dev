"""Shared stock pool across the size variants of one product - in EXACT base units.

A product sold as "250 g" and "1 kg" has one physical stock of the product, not
one per size. Stock is held in lots whose authoritative quantity is an integer
number of BASE units of the unit family (grams / ml / pieces; see
`app.services.units`). Every size of the family draws from the same pool and
sells `floor(base / size_base)` whole packs - there is no per-size copy of the
stock, so the same physical stock is never counted twice:

    physical lot stock  =  shared pool (ordinary lots)
                         + size-specific stock (share lots, one size only)
    available           =  physical - reserved            (all integers)
    a size can sell     =  floor((shared pool + that size's own share) / size_base)

Lots whose legacy pack quantity could not be converted exactly are quarantined
(NULL base): they are never counted here.

BOX, PACK and anything else outside g/ml/pieces are their own dimension and pool
only with identical units (no invented conversion).
"""

from collections import defaultdict
from decimal import ROUND_DOWN, Decimal

from sqlalchemy.orm import Session

from app.exceptions.base import BusinessValidationError
from app.models.inventory_lot import InventoryLot
from app.models.product_variant import ProductVariant
from app.services import units as U

_QTY = Decimal("0.001")
_ZERO = Decimal("0")


def variant_size(variant: ProductVariant) -> tuple[str, int]:
    """(dimension, base units in one pack) of `variant`."""
    return U.dimension_of(variant.unit), U.size_base(variant.quantity, variant.unit)


def amount_in_base(amount: Decimal, unit: str) -> tuple[str, int]:
    """(dimension, exact integer base units) for a weight/volume/count amount."""
    return U.dimension_of(unit), U.to_base(amount, unit)


def to_packs(base_amount: Decimal | int, pack_size: Decimal | int) -> Decimal:
    """Display-only: base units as a 3-decimal pack count (rounded DOWN).

    Never used for accounting - lots hold exact base units."""
    if pack_size <= 0:
        return _ZERO
    return (Decimal(base_amount) / Decimal(pack_size)).quantize(_QTY, rounding=ROUND_DOWN)


def weight_to_packs(variant: ProductVariant, amount: Decimal, amount_unit: str) -> Decimal:
    """Display/API helper: packs of `variant` that `amount` of `amount_unit` makes
    (1 kg of a 250 g variant -> 4 packs). The unit must be in the variant's
    dimension. Accounting never goes through this - it uses `amount_in_base`."""
    family = U.dimension_of(amount_unit)
    if family != U.dimension_of(variant.unit) or family not in U.CONVERTIBLE:
        raise BusinessValidationError(
            f"{amount_unit} cannot be converted to packs of {variant.unit}; enter a number of packs instead."
        )
    packs = to_packs(U.to_base(amount, amount_unit), U.size_base(variant.quantity, variant.unit))
    if packs <= 0:
        raise BusinessValidationError("That amount is smaller than one pack-thousandth; enter a larger amount.")
    return packs


def display_amount(family: str, base_amount: int | Decimal) -> tuple[Decimal, str]:
    """A base-unit amount as people read it: g -> kg, ml -> L, pieces as is."""
    return U.display_amount(family, base_amount)


def pool_siblings(db: Session, variant: ProductVariant) -> list[ProductVariant]:
    """Variants of the same product in the same unit family (incl. itself)."""
    family = U.dimension_of(variant.unit)
    return [
        v
        for v in db.query(ProductVariant)
        .filter(ProductVariant.product_id == variant.product_id)
        .order_by(ProductVariant.id.asc())
        .all()
        if U.dimension_of(v.unit) == family
    ]


def pool_base_amounts(
    db: Session, product_ids: set[int] | list[int]
) -> tuple[dict[tuple[int, str], int], list[ProductVariant], dict[int, int]]:
    """Sellable stock in the family's base unit (g / ml / pieces), minus
    reservations, from ACTIVE lots with a trusted base quantity:

    * the shared pool per (product, unit family) - every ordinary lot, which
      all sizes of the family draw from, and
    * what each variant has been assigned (its share lots), which only that
      size can sell.

    Also returns the products' variants so callers do not have to re-query."""
    variants = (
        db.query(ProductVariant).filter(ProductVariant.product_id.in_(list(product_ids))).all()
        if product_ids
        else []
    )
    by_id = {v.id: v for v in variants}
    lots = (
        db.query(InventoryLot)
        .filter(
            InventoryLot.variant_id.in_(list(by_id)),
            InventoryLot.status == "ACTIVE",
            InventoryLot.quantity_base.is_not(None),
        )
        .all()
        if by_id
        else []
    )
    pool: dict[tuple[int, str], int] = defaultdict(int)
    shares: dict[int, int] = defaultdict(int)
    for lot in lots:
        owner = by_id[lot.variant_id]
        available = lot.quantity_base - lot.reserved_base
        if available > 0:
            if lot.is_share:
                shares[owner.id] += available
            else:
                pool[(owner.product_id, U.dimension_of(owner.unit))] += available
    return pool, variants, shares


def available_packs_by_variant(db: Session, variant_ids: list[int]) -> dict[int, Decimal]:
    """Whole packs each variant can sell, from the product's shared pool plus its
    own share. Customers can only buy whole packs: 1.1 kg of 250 g packs is 4."""
    if not variant_ids:
        return {}
    wanted = db.query(ProductVariant).filter(ProductVariant.id.in_(variant_ids)).all()
    pool, _, shares = pool_base_amounts(db, {v.product_id for v in wanted})
    return {
        v.id: Decimal(U.packs_for(pool[(v.product_id, U.dimension_of(v.unit))] + shares[v.id], v.size_base))
        for v in wanted
    }
