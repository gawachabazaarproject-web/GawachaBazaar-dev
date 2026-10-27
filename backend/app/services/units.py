"""The ONE place unit conversion lives (backend). Pure - no DB, no floats.

Inventory is accounted in integer BASE units of a dimension:

    MASS   -> grams (g)         KG = 1000, G = 1
    VOLUME -> millilitres (ml)  L  = 1000, ML = 1
    COUNT  -> pieces            DOZEN = 12, UNIT = 1
    BOX / PACK -> their own dimension, 1 base unit per BOX / PACK (no invented conversion)

A product size ("250 g", "1 kg", "1 dozen") is only a conversion factor
(`size_base`, an integer number of base units); packs are a DISPLAY / SALE
quantity derived from base units with `packs_for`, never stored as the truth.
Mass is never converted to volume or count (`ensure_same_dimension`).

Clients (Admin, mobile) must not carry their own factor tables: the API returns
normalised values and `Admin/lib/units.ts` / `mobile/src/utils/units.ts` mirror
this table and are checked against it by `tests/test_units_parity.py`.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.exceptions.base import BusinessValidationError

MASS = "MASS"
VOLUME = "VOLUME"
COUNT = "COUNT"
# Dimensions whose units convert into each other (box/pack stand alone).
CONVERTIBLE = (MASS, VOLUME, COUNT)


@dataclass(frozen=True)
class UnitInfo:
    dimension: str
    factor: int  # base units per 1 of this unit
    base_label: str  # label of the dimension's base unit
    label: str  # how this unit is written


UNITS: dict[str, UnitInfo] = {
    "KG": UnitInfo(MASS, 1000, "g", "kg"),
    "G": UnitInfo(MASS, 1, "g", "g"),
    "L": UnitInfo(VOLUME, 1000, "ml", "L"),
    "ML": UnitInfo(VOLUME, 1, "ml", "ml"),
    "UNIT": UnitInfo(COUNT, 1, "pc", "pc"),
    "DOZEN": UnitInfo(COUNT, 12, "pc", "dozen"),
    "BOX": UnitInfo("BOX", 1, "box", "box"),
    "PACK": UnitInfo("PACK", 1, "pack", "pack"),
    "CRATE": UnitInfo("CRATE", 1, "crate", "crate"),
}

# Units an admin may type a stock amount in (BOX/PACK are counted in packs only).
AMOUNT_UNITS = ("KG", "G", "L", "ML", "UNIT", "DOZEN")


def info(unit: str) -> UnitInfo:
    try:
        return UNITS[unit]
    except KeyError:
        raise BusinessValidationError(f"Unknown unit {unit!r}.") from None


def dimension_of(unit: str) -> str:
    return info(unit).dimension


def ensure_same_dimension(a_unit: str, b_unit: str) -> str:
    da, db = dimension_of(a_unit), dimension_of(b_unit)
    if da != db:
        raise BusinessValidationError(f"{a_unit} cannot be converted to {b_unit} ({da} vs {db}).")
    return da


def to_base(amount: Decimal, unit: str) -> int:
    """`amount` of `unit` as an exact integer number of base units.

    Raises when it is not a whole number of base units (e.g. 0.0005 kg = 0.5 g):
    inventory never stores a quantity it would have to round."""
    base = Decimal(amount) * info(unit).factor
    whole = base.to_integral_value()
    if base != whole:
        raise BusinessValidationError(
            f"{amount} {info(unit).label} is not a whole number of {info(unit).base_label}; "
            "enter a smaller unit."
        )
    return int(whole)


def size_base(quantity: Decimal, unit: str) -> int:
    """Base units in ONE pack of a size (variant): quantity x unit."""
    value = to_base(quantity, unit)
    if value <= 0:
        raise BusinessValidationError("A size must be larger than zero.")
    return value


def packs_for(base: int, size: int) -> int:
    """Whole packs a base quantity can sell (floor). Never more than there is."""
    return base // size if size > 0 and base > 0 else 0


def packs_exact(base: int, size: int) -> Decimal:
    """Base quantity as a (display-only) pack count, 3 decimals like the legacy columns."""
    return (Decimal(base) / Decimal(size)).quantize(Decimal("0.001")) if size > 0 else Decimal(0)


def base_to_amount(base: int, unit: str) -> Decimal:
    """Base units as an amount of `unit` (display), exact: 2500 g, KG -> 2.5."""
    return Decimal(base) / info(unit).factor


def display_unit(dimension: str) -> tuple[str, int]:
    """(label, factor) of the unit people read a dimension in: kg / L / pcs."""
    return {MASS: ("kg", 1000), VOLUME: ("L", 1000), COUNT: ("pcs", 1)}.get(
        dimension, (dimension.lower(), 1)
    )


def display_amount(dimension: str, base: int | Decimal) -> tuple[Decimal, str]:
    label, factor = display_unit(dimension)
    return (Decimal(base) / factor).quantize(Decimal("0.001")), label


def amount_text(base: int | Decimal, dimension: str) -> str:
    """Human text for a base quantity: '68.999 kg', '12 pcs', '2.5 L'."""
    amount, label = display_amount(dimension, base)
    return f"{amount.normalize():f} {label}"
