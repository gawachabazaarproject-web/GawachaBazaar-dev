"""Shared stock pool across the size variants of one product.

A product sold as "250 g" and "1 kg" has one physical stock of the product,
not one per size. Stock is entered as lots against whichever variant the
admin chose (usually the 1 kg one); every sibling variant of the same unit
family draws from the same pool, converted through each variant's size
(`quantity` x unit).

Lot quantities are expressed in packs of the lot's own variant, so a lot of
5 against a 1 kg variant holds 5 kg. Conversion is only possible inside one
unit family (KG/G, L/ML, UNIT/DOZEN); BOX, PACK and anything unknown are
their own family and pool only with identical units.
"""

from collections import defaultdict
from decimal import ROUND_DOWN, Decimal

from sqlalchemy.orm import Session

from app.models.inventory_lot import InventoryLot
from app.models.product_variant import ProductVariant

_QTY = Decimal("0.001")
_ZERO = Decimal("0")

# unit -> (family, factor to that family's base unit)
_UNIT_FAMILIES: dict[str, tuple[str, Decimal]] = {
    "KG": ("MASS", Decimal("1000")),
    "G": ("MASS", Decimal("1")),
    "L": ("VOLUME", Decimal("1000")),
    "ML": ("VOLUME", Decimal("1")),
    "UNIT": ("COUNT", Decimal("1")),
    "DOZEN": ("COUNT", Decimal("12")),
}


def variant_size(variant: ProductVariant) -> tuple[str, Decimal]:
    """(family, size in the family's base unit) of one pack of `variant`."""
    family, factor = _UNIT_FAMILIES.get(variant.unit, (variant.unit, Decimal("1")))
    return family, variant.quantity * factor


def to_packs(base_amount: Decimal, pack_size: Decimal) -> Decimal:
    """Whole-thousandth number of packs of `pack_size` inside `base_amount`.

    Rounds down so a pool is never reported as holding more than it has."""
    if pack_size <= 0:
        return _ZERO
    return (base_amount / pack_size).quantize(_QTY, rounding=ROUND_DOWN)


def pool_siblings(db: Session, variant: ProductVariant) -> list[ProductVariant]:
    """Variants of the same product in the same unit family (incl. itself)."""
    family, _ = variant_size(variant)
    return [
        v
        for v in db.query(ProductVariant)
        .filter(ProductVariant.product_id == variant.product_id)
        .order_by(ProductVariant.id.asc())
        .all()
        if variant_size(v)[0] == family
    ]


def available_packs_by_variant(
    db: Session, variant_ids: list[int]
) -> dict[int, Decimal]:
    """Sellable packs per variant, computed from the product's shared pool.

    Counts ACTIVE lots only and subtracts reservations, like the per-lot
    "available" figure, but pools every same-family sibling's lots first.
    """
    if not variant_ids:
        return {}
    wanted = db.query(ProductVariant).filter(ProductVariant.id.in_(variant_ids)).all()
    product_ids = {v.product_id for v in wanted}
    variants = (
        db.query(ProductVariant).filter(ProductVariant.product_id.in_(product_ids)).all()
    )
    by_id = {v.id: v for v in variants}
    lots = (
        db.query(InventoryLot)
        .filter(
            InventoryLot.variant_id.in_(list(by_id)),
            InventoryLot.status == "ACTIVE",
        )
        .all()
    )

    pool: dict[tuple[int, str], Decimal] = defaultdict(lambda: _ZERO)
    for lot in lots:
        owner = by_id[lot.variant_id]
        family, size = variant_size(owner)
        available = lot.quantity - lot.reserved_quantity
        if available > 0:
            pool[(owner.product_id, family)] += available * size

    result: dict[int, Decimal] = {}
    for v in wanted:
        family, size = variant_size(v)
        result[v.id] = to_packs(pool[(v.product_id, family)], size)
    return result
