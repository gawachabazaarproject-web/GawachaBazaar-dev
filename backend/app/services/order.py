"""Order domain service: order reads and checkout orchestration.

TRANSACTION DESIGN: same rule as Cart/Inventory/Packaging - every route
here is protected by `require_roles`, which composes `get_current_user` and
therefore always autobegins the session's transaction via its own reads
before any service method runs. `checkout` never calls `db.begin()`; it
performs the locking SELECTs, validation, and writes directly against the
already-open transaction, then calls `db.commit()` exactly once.

CHECKOUT RETRY SAFETY: `checkout` locates the user's cart by `user_id`
ordered by `id DESC` - deliberately WITHOUT filtering by `status = 'ACTIVE'`
in the locking query. Under PostgreSQL READ COMMITTED, a `SELECT ... FOR
UPDATE` that blocked on a row later excluded by its own WHERE clause (e.g.
status changed by the transaction that held the lock) returns NO rows once
unblocked, not the updated row - so filtering by status here would make a
second concurrent request see "no cart" instead of the newly-CHECKED_OUT
one, breaking the "return the existing order" requirement entirely. Locking
unconditionally on `user_id` and branching on `status` *after* acquiring
the lock is what makes retry safety actually work.

PHASE 15 ADDITION: `checkout` now also creates the order's inventory
reservation (via InventoryReservationService.create_reservation_for_order)
before the single commit below, so reservation creation is part of the
same atomic transaction as order creation - if FIFO allocation fails
(insufficient stock), the exception propagates, nothing commits, and the
whole checkout (order, items, address, cart status change) rolls back
together. Checkout itself never decides COD vs UPI or creates a Payment -
that remains PaymentService's responsibility (POST /payments), unchanged
from Phase 14. See app/services/inventory_reservation.py for why.
"""

import secrets
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions.base import ConflictError, NotFoundError
from app.models.address import Address
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.order import Order
from app.models.order_address import OrderAddress
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.schemas.order import (
    CheckoutRequest,
    OrderAddressResponse,
    OrderDetailResponse,
    OrderItemResponse,
    OrderListResponse,
    OrderResponse,
)
from app.services.inventory_reservation import InventoryReservationService
from app.services.pricing import get_current_prices_for_variants

_ACTIVE = "ACTIVE"
_CHECKED_OUT = "CHECKED_OUT"
_ABANDONED = "ABANDONED"
_CENTS = Decimal("0.01")


class OrderService:
    """Order reads (user-scoped) and the atomic checkout transaction."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Reads (always scoped to the requesting user)
    # ------------------------------------------------------------------

    def list_orders(
        self, user_id: int, page: int, page_size: int
    ) -> OrderListResponse:
        query = self.db.query(Order).filter(Order.user_id == user_id)
        total = query.count()
        items = (
            query.order_by(Order.placed_at.desc(), Order.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return OrderListResponse(
            items=[OrderResponse.model_validate(o) for o in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_order_detail(self, user_id: int, order_id: int) -> OrderDetailResponse:
        order = (
            self.db.query(Order)
            .filter(Order.id == order_id, Order.user_id == user_id)
            .first()
        )
        if not order:
            # Also covers "exists but belongs to another user" - both are
            # 404 to avoid cross-user resource disclosure.
            raise NotFoundError("Order not found.")
        return self._to_order_detail(order)

    # ------------------------------------------------------------------
    # Checkout (the atomic business transaction)
    # ------------------------------------------------------------------

    def checkout(self, user_id: int, data: CheckoutRequest) -> tuple[OrderDetailResponse, bool]:
        """Returns (order, created) - created=False when this call found an
        already-CHECKED_OUT cart and returned its existing order instead of
        creating a new one (the retry-safety path).
        """
        cart = (
            self.db.query(Cart)
            .filter(Cart.user_id == user_id)
            .order_by(Cart.id.desc())
            .with_for_update()
            .first()
        )
        if not cart:
            raise NotFoundError("No cart found. Add items before checking out.")

        if cart.status == _CHECKED_OUT:
            existing_order = (
                self.db.query(Order).filter(Order.cart_id == cart.id).first()
            )
            if not existing_order:
                # Should be unreachable given the CHECKED_OUT + UNIQUE(cart_id)
                # invariant, but fail safely rather than fabricate an order.
                raise ConflictError("This cart has already been checked out.")
            return self._to_order_detail(existing_order), False

        if cart.status == _ABANDONED:
            raise ConflictError("This cart has been abandoned and cannot be checked out.")

        # status == ACTIVE from here.
        items = (
            self.db.query(CartItem)
            .filter(CartItem.cart_id == cart.id)
            .order_by(CartItem.variant_id)
            .all()
        )
        if not items:
            raise ConflictError("Cannot checkout an empty cart.")

        variant_ids = sorted({i.variant_id for i in items})
        variants = {
            v.id: v
            for v in self.db.query(ProductVariant)
            .filter(ProductVariant.id.in_(variant_ids))
            .order_by(ProductVariant.id)
            .with_for_update()
            .all()
        }

        product_ids = {v.product_id for v in variants.values()}
        products = {
            p.id: p
            for p in self.db.query(Product).filter(Product.id.in_(product_ids)).all()
        }

        for variant_id in variant_ids:
            variant = variants.get(variant_id)
            if not variant:
                raise NotFoundError(f"Product variant {variant_id} not found.")
            if variant.status != _ACTIVE:
                raise ConflictError(
                    f"Product variant {variant.sku} is no longer available."
                )
            product = products.get(variant.product_id)
            if not product or product.status != _ACTIVE:
                raise ConflictError(
                    f"Product for variant {variant.sku} is no longer available."
                )

        prices = get_current_prices_for_variants(self.db, variant_ids)
        missing = [v_id for v_id in variant_ids if v_id not in prices]
        if missing:
            raise ConflictError(
                "One or more cart items no longer have a valid price."
            )

        currencies = {p.currency for p in prices.values()}
        if len(currencies) > 1:
            raise ConflictError(
                "Cart items have mixed currencies and cannot be checked out."
            )
        currency = next(iter(currencies))

        address = (
            self.db.query(Address)
            .filter(Address.id == data.address_id, Address.user_id == user_id)
            .first()
        )
        if not address:
            # Never distinguish "doesn't exist" from "belongs to someone
            # else" - both are 404.
            raise NotFoundError("Address not found.")

        order_item_rows = []
        total_amount = Decimal("0")
        for item in items:
            variant = variants[item.variant_id]
            product = products[variant.product_id]
            price = prices[item.variant_id]
            line_total = (item.quantity * price.price).quantize(
                _CENTS, rounding=ROUND_HALF_UP
            )
            total_amount += line_total
            order_item_rows.append(
                {
                    "variant_id": variant.id,
                    "product_name": product.name,
                    "variant_name": variant.name,
                    "sku": variant.sku,
                    "unit": variant.unit,
                    "quantity": item.quantity,
                    "unit_price": price.price,
                    "total_price": line_total,
                }
            )

        order = Order(
            user_id=user_id,
            cart_id=cart.id,
            order_number=self._generate_order_number(),
            status="PENDING",
            total_amount=total_amount,
            currency=currency,
            placed_at=datetime.now(UTC),
        )
        self.db.add(order)
        self.db.flush()  # assign order.id for FK references below

        created_items = []
        for row in order_item_rows:
            order_item = OrderItem(order_id=order.id, **row)
            self.db.add(order_item)
            created_items.append(order_item)
        self.db.flush()  # assign order_item.id, needed by reservation allocation

        InventoryReservationService(self.db).create_reservation_for_order(
            order, created_items
        )

        self.db.add(
            OrderAddress(
                order_id=order.id,
                address_line_1=address.address_line_1,
                address_line_2=address.address_line_2,
                city=address.city,
                state=address.state,
                postal_code=address.postal_code,
                latitude=address.latitude,
                longitude=address.longitude,
            )
        )

        cart.status = _CHECKED_OUT

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not complete checkout due to a conflicting update."
            ) from exc

        return self._to_order_detail(order), True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_order_number() -> str:
        """Date-prefixed + high-entropy random suffix - not timestamp-only,
        not client-trusted. The DB's UNIQUE(order_number) is the final
        safety boundary if this ever collides (astronomically unlikely).
        """
        return f"ORD{datetime.now(UTC):%Y%m%d}{secrets.token_hex(4).upper()}"

    def _to_order_detail(self, order: Order) -> OrderDetailResponse:
        items = (
            self.db.query(OrderItem)
            .filter(OrderItem.order_id == order.id)
            .order_by(OrderItem.id)
            .all()
        )
        address = (
            self.db.query(OrderAddress)
            .filter(OrderAddress.order_id == order.id)
            .first()
        )
        return OrderDetailResponse(
            **OrderResponse.model_validate(order).model_dump(),
            items=[OrderItemResponse.model_validate(i) for i in items],
            address=OrderAddressResponse.model_validate(address) if address else None,
        )
