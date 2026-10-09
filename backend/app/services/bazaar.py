"""Bazaar offer: cart delivery quote and Gawacha Bazaar+ eligibility.

A "Bazaar" is a basket/order with FREE_DELIVERY_MIN_ITEMS or more DIFFERENT
PRODUCTS (the same product in two sizes counts once). A customer with
BAZAAR_PLUS_ORDERS_REQUIRED Bazaar orders in the current calendar month
(BAZAAR_TIMEZONE, default IST) is eligible for Gawacha Bazaar+. Cancelled
and expired orders do not count.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.address import Address
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product_variant import ProductVariant
from app.schemas.bazaar import BazaarStatusResponse, DeliveryQuoteResponse
from app.services.delivery import calculate_delivery_fee, distinct_product_count, get_packing_point

_NOT_COUNTED = ("CANCELLED", "EXPIRED")


def month_start(now: datetime | None = None) -> datetime:
    """Midnight on the 1st of the current month in BAZAAR_TIMEZONE (aware)."""
    tz = ZoneInfo(settings.BAZAAR_TIMEZONE)
    local = (now or datetime.now(tz)).astimezone(tz)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class BazaarService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _cart_product_count(self, user_id: int) -> int:
        cart = (
            self.db.query(Cart)
            .filter(Cart.user_id == user_id, Cart.status == "ACTIVE")
            .order_by(Cart.id.desc())
            .first()
        )
        if not cart:
            return 0
        rows = (
            self.db.query(ProductVariant.product_id)
            .join(CartItem, CartItem.variant_id == ProductVariant.id)
            .filter(CartItem.cart_id == cart.id)
            .all()
        )
        return distinct_product_count(r[0] for r in rows)

    def delivery_quote(self, user_id: int, address_id: int | None) -> DeliveryQuoteResponse:
        lat = lon = None
        if address_id is not None:
            address = (
                self.db.query(Address)
                .filter(Address.id == address_id, Address.user_id == user_id)
                .first()
            )
            if address:
                lat, lon = address.latitude, address.longitude
        quote = calculate_delivery_fee(
            self._cart_product_count(user_id), lat, lon, origin=get_packing_point(self.db)
        )
        return DeliveryQuoteResponse(
            fee=quote.fee,
            free_delivery=quote.free_delivery,
            item_count=quote.item_count,
            free_delivery_min_items=quote.free_delivery_min_items,
            items_to_free_delivery=quote.items_to_free_delivery,
            distance_km=quote.distance_km,
            distance_estimated=quote.distance_estimated,
            currency="INR",
        )

    def status(self, user_id: int) -> BazaarStatusResponse:
        products_per_order = (
            self.db.query(func.count(func.distinct(ProductVariant.product_id)).label("products"))
            .select_from(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .join(ProductVariant, ProductVariant.id == OrderItem.variant_id)
            .filter(
                Order.user_id == user_id,
                Order.placed_at >= month_start(),
                Order.status.notin_(_NOT_COUNTED),
            )
            .group_by(Order.id)
            .subquery()
        )
        bazaar_orders = (
            self.db.query(func.count())
            .select_from(products_per_order)
            .filter(products_per_order.c.products >= settings.FREE_DELIVERY_MIN_ITEMS)
            .scalar()
            or 0
        )
        return BazaarStatusResponse(
            free_delivery_min_items=settings.FREE_DELIVERY_MIN_ITEMS,
            cart_item_count=self._cart_product_count(user_id),
            bazaar_orders_in_window=bazaar_orders,
            orders_required=settings.BAZAAR_PLUS_ORDERS_REQUIRED,
            period="month",
            eligible_for_bazaar_plus=bazaar_orders >= settings.BAZAAR_PLUS_ORDERS_REQUIRED,
        )
