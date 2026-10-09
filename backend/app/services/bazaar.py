"""Bazaar offer: cart delivery quote and Gawacha Bazaar+ eligibility.

A "Bazaar" is an order of FREE_DELIVERY_MIN_ITEMS or more units. A customer
with BAZAAR_PLUS_ORDERS_REQUIRED Bazaar orders inside the last
BAZAAR_PLUS_WINDOW_DAYS days (rolling, not calendar week) is eligible for
Gawacha Bazaar+. Cancelled and expired orders do not count.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.address import Address
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.schemas.bazaar import BazaarStatusResponse, DeliveryQuoteResponse
from app.services.delivery import calculate_delivery_fee, item_count_for_quantities

_NOT_COUNTED = ("CANCELLED", "EXPIRED")


class BazaarService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _active_cart_quantities(self, user_id: int) -> list:
        cart = (
            self.db.query(Cart)
            .filter(Cart.user_id == user_id, Cart.status == "ACTIVE")
            .order_by(Cart.id.desc())
            .first()
        )
        if not cart:
            return []
        rows = self.db.query(CartItem.quantity).filter(CartItem.cart_id == cart.id).all()
        return [r[0] for r in rows]

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
            item_count_for_quantities(self._active_cart_quantities(user_id)), lat, lon
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
        since = datetime.now(UTC) - timedelta(days=settings.BAZAAR_PLUS_WINDOW_DAYS)
        units_per_order = (
            self.db.query(func.sum(OrderItem.quantity).label("units"))
            .join(Order, Order.id == OrderItem.order_id)
            .filter(
                Order.user_id == user_id,
                Order.placed_at >= since,
                Order.status.notin_(_NOT_COUNTED),
            )
            .group_by(Order.id)
            .subquery()
        )
        bazaar_orders = (
            self.db.query(func.count())
            .select_from(units_per_order)
            .filter(units_per_order.c.units >= settings.FREE_DELIVERY_MIN_ITEMS)
            .scalar()
            or 0
        )
        return BazaarStatusResponse(
            free_delivery_min_items=settings.FREE_DELIVERY_MIN_ITEMS,
            cart_item_count=item_count_for_quantities(self._active_cart_quantities(user_id)),
            bazaar_orders_in_window=bazaar_orders,
            orders_required=settings.BAZAAR_PLUS_ORDERS_REQUIRED,
            window_days=settings.BAZAAR_PLUS_WINDOW_DAYS,
            eligible_for_bazaar_plus=bazaar_orders >= settings.BAZAAR_PLUS_ORDERS_REQUIRED,
        )
