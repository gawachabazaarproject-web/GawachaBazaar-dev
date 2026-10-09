"""Items whose stock needs attention: out, at/below their reserve level, or
running close to it (see app/services/stock_levels.py for the rule). Feeds the
dashboard's Low stock card and the Admin's header alerts, so both always agree.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.inventory_lot import InventoryLot
from app.models.product import Product
from app.models.product_variant import ProductVariant
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
    available: Decimal
    reserve_level: Decimal  # the reserve in force (own setting, else the default)
    level: str  # OUT / BELOW / NEAR


def list_stock_alerts(db: Session) -> list[StockAlert]:
    """Per ACTIVE variant of an ACTIVE product, available stock summed across
    its active lots (a variant with no stock record counts as 0), most urgent
    first. One nearly-empty lot is not an alert if another lot is full."""
    available = func.coalesce(func.sum(InventoryLot.quantity - InventoryLot.reserved_quantity), 0)
    rows = (
        db.query(
            Product.id,
            ProductVariant.id,
            Product.name,
            ProductVariant.name,
            ProductVariant.unit,
            ProductVariant.reserve_level,
            available,
        )
        .select_from(ProductVariant)
        .join(Product, Product.id == ProductVariant.product_id)
        .outerjoin(
            InventoryLot,
            (InventoryLot.variant_id == ProductVariant.id) & (InventoryLot.status != "INACTIVE"),
        )
        .filter(ProductVariant.status == "ACTIVE", Product.status == "ACTIVE")
        .group_by(
            Product.id, ProductVariant.id, Product.name, ProductVariant.name, ProductVariant.unit,
            ProductVariant.reserve_level,
        )
        .all()
    )
    alerts: list[StockAlert] = []
    for product_id, variant_id, product_name, variant_name, unit, reserve, avail in rows:
        avail = max(Decimal(avail), Decimal("0"))
        level = stock_level(avail, reserve)
        if level in ALERT_LEVELS:
            alerts.append(
                StockAlert(
                    product_id, variant_id, product_name, variant_name, unit, avail,
                    effective_reserve(reserve), level,
                )
            )
    alerts.sort(key=lambda a: (_SEVERITY[a.level], a.available / (a.reserve_level or Decimal("1")), a.variant_id))
    return alerts


def count_by_level(alerts: list[StockAlert]) -> dict[str, int]:
    return {level: sum(1 for a in alerts if a.level == level) for level in (OUT, BELOW, NEAR)}
