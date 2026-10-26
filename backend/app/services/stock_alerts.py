"""Items whose stock needs attention: out, at/below their reserve level, or
running close to it (see app/services/stock_levels.py for the rule). Feeds the
dashboard's Low stock card and the Admin's header alerts, so both always agree.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.services.stock_levels import (
    ALERT_LEVELS,
    BELOW,
    NEAR,
    OUT,
    effective_reserve,
    product_status,
    stock_level,
)
from app.services.stock_pool import available_packs_by_variant

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


def count_products(db: Session, alerts: list[StockAlert]) -> dict[str, int]:
    """Products (not sizes) that are out / low, using the same rule as the
    Inventory page (`product_status`): "Tomato" is one product even when three
    of its sizes are running low."""
    sizes_per_product = dict(
        db.query(ProductVariant.product_id, func.count(ProductVariant.id))
        .join(Product, Product.id == ProductVariant.product_id)
        .filter(ProductVariant.status == "ACTIVE", Product.status == "ACTIVE")
        .group_by(ProductVariant.product_id)
        .all()
    )
    levels: dict[int, list[str]] = {}
    for alert in alerts:
        levels.setdefault(alert.product_id, []).append(alert.level)
    counts = {"OUT": 0, "LOW": 0}
    for product_id, size_count in sizes_per_product.items():
        found = levels.get(product_id, [])
        # Sizes with no alert are comfortably stocked.
        status = product_status(found + ["OK"] * (size_count - len(found)))
        if status in counts:
            counts[status] += 1
    return counts
