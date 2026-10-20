"""Items whose stock needs attention: out, at/below their reserve level, or
running close to it (see app/services/stock_levels.py for the rule). Feeds the
dashboard's Low stock card and the Admin's header alerts, so both always agree.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.services.stock_pool import available_packs_by_variant
from app.services.stock_levels import (
    ALERT_LEVELS,
    BELOW,
    NEAR,
    OUT,
    effective_reserve,
    stock_level,
)

_SEVERITY = {OUT: 0, BELOW: 1, NEAR: 2}


@dataclass(frozen=True)
class StockAlert:
    product_id: int
    variant_id: int
    product_name: str
    variant_name: str
    unit: str
    pack_quantity: Decimal  # size of one pack, in `unit`
    available: Decimal  # whole packs this size can sell
    reserve_level: Decimal  # the reserve in force (own setting, else the default)
    level: str  # OUT / BELOW / NEAR


def list_stock_alerts(db: Session) -> list[StockAlert]:
    """Per ACTIVE variant of an ACTIVE product, the packs it can actually
    sell: its own assigned share plus the product's shared stock (see
    app/services/stock_pool.py), the same number the product page and the app
    use - so a size that still sells from the shared pool is never reported
    as out of stock. A variant with no stock counts as 0. Most urgent first."""
    rows = (
        db.query(
            Product.id,
            ProductVariant.id,
            Product.name,
            ProductVariant.name,
            ProductVariant.unit,
            ProductVariant.quantity,
            ProductVariant.reserve_level,
        )
        .select_from(ProductVariant)
        .join(Product, Product.id == ProductVariant.product_id)
        .filter(ProductVariant.status == "ACTIVE", Product.status == "ACTIVE")
        .all()
    )
    packs = available_packs_by_variant(db, [r[1] for r in rows])
    alerts: list[StockAlert] = []
    for product_id, variant_id, product_name, variant_name, unit, quantity, reserve in rows:
        avail = max(packs.get(variant_id, Decimal("0")), Decimal("0"))
        level = stock_level(avail, reserve)
        if level in ALERT_LEVELS:
            alerts.append(
                StockAlert(
                    product_id, variant_id, product_name, variant_name, unit, quantity, avail,
                    effective_reserve(reserve), level,
                )
            )
    alerts.sort(key=lambda a: (_SEVERITY[a.level], a.available / (a.reserve_level or Decimal("1")), a.variant_id))
    return alerts


def count_by_level(alerts: list[StockAlert]) -> dict[str, int]:
    return {level: sum(1 for a in alerts if a.level == level) for level in (OUT, BELOW, NEAR)}
