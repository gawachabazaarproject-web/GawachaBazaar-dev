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

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.exceptions.base import BusinessValidationError, ConflictError, NotFoundError
from app.models.address import Address
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.fulfillment import Fulfillment
from app.models.order import Order
from app.models.order_address import OrderAddress
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.refund import Refund
from app.models.user import User
from app.schemas.admin_order import (
    AdminOrderDetailResponse,
    AdminOrderListItemResponse,
    AdminOrderListResponse,
)
from app.schemas.fulfillment import FulfillmentResponse
from app.schemas.order import (
    CheckoutRequest,
    OrderAddressResponse,
    OrderDetailResponse,
    OrderItemResponse,
    OrderListResponse,
    OrderResponse,
)
from app.schemas.payment import PaymentResponse
from app.schemas.refund import AdminRefundResponse
from app.services.admin_audit import AdminAuditService
from app.services.inventory_reservation import InventoryReservationService
from app.services.order_state import (
    IllegalOrderTransitionError,
    OrderStatus,
    transition_order_status,
)
from app.services.pricing import get_current_prices_for_variants
from app.services.promotion import CartLineForPromo, PromotionService
from app.services.refund import RefundService

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
    # Admin reads (Admin Panel Phase 2/3) - unscoped by owner, gated by
    # `require_permission("orders.read")` at the route level, not
    # ownership. Every field returned is read straight off the same
    # authoritative rows the customer-facing endpoints use - total_amount
    # is never recomputed, and payment/fulfillment/refund status are the
    # backend's own state-machine values (see order_state.py /
    # payment_state.py / fulfillment_state.py / refund_state.py), not a
    # frontend interpretation of them.
    # ------------------------------------------------------------------

    def admin_list_orders(
        self,
        page: int,
        page_size: int,
        status: str | None = None,
        payment_status: str | None = None,
        fulfillment_status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        q: str | None = None,
        user_id: int | None = None,
    ) -> AdminOrderListResponse:
        query = self.db.query(Order).join(User, Order.user_id == User.id)

        if user_id is not None:
            query = query.filter(Order.user_id == user_id)
        if status:
            query = query.filter(Order.status == status)
        if date_from:
            query = query.filter(Order.placed_at >= date_from)
        if date_to:
            query = query.filter(Order.placed_at <= date_to)
        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(
                    Order.order_number.ilike(like),
                    User.name.ilike(like),
                    User.email.ilike(like),
                    User.phone.ilike(like),
                )
            )
        if payment_status:
            query = query.join(Payment, Payment.order_id == Order.id).filter(
                Payment.status == payment_status
            )
        if fulfillment_status:
            query = query.join(Fulfillment, Fulfillment.order_id == Order.id).filter(
                Fulfillment.status == fulfillment_status
            )

        total = query.count()
        orders = (
            query.order_by(Order.placed_at.desc(), Order.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        if not orders:
            return AdminOrderListResponse(items=[], page=page, page_size=page_size, total=total)

        order_ids = [o.id for o in orders]
        customers = {u.id: u for u in self.db.query(User).filter(User.id.in_({o.user_id for o in orders}))}
        payments = {
            p.order_id: p
            for p in self.db.query(Payment).filter(Payment.order_id.in_(order_ids))
        }
        fulfillments = {
            f.order_id: f
            for f in self.db.query(Fulfillment).filter(Fulfillment.order_id.in_(order_ids))
        }
        item_counts = dict(
            self.db.query(OrderItem.order_id, func.count(OrderItem.id))
            .filter(OrderItem.order_id.in_(order_ids))
            .group_by(OrderItem.order_id)
            .all()
        )

        items = []
        for order in orders:
            customer = customers[order.user_id]
            payment = payments.get(order.id)
            fulfillment = fulfillments.get(order.id)
            items.append(
                AdminOrderListItemResponse(
                    id=order.id,
                    order_number=order.order_number,
                    status=order.status,
                    total_amount=order.total_amount,
                    discount_amount=order.discount_amount,
                    applied_promo_code=order.applied_promo_code,
                    currency=order.currency,
                    placed_at=order.placed_at,
                    customer_id=customer.id,
                    customer_name=customer.name,
                    customer_email=customer.email,
                    item_count=item_counts.get(order.id, 0),
                    payment_status=payment.status if payment else None,
                    payment_method=payment.payment_method if payment else None,
                    fulfillment_status=fulfillment.status if fulfillment else None,
                    delivery_partner_user_id=(
                        fulfillment.delivery_partner_user_id if fulfillment else None
                    ),
                )
            )

        return AdminOrderListResponse(items=items, page=page, page_size=page_size, total=total)

    def admin_get_order_detail(self, order_id: int) -> AdminOrderDetailResponse:
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise NotFoundError("Order not found.")

        customer = self.db.query(User).filter(User.id == order.user_id).first()
        payment = self.db.query(Payment).filter(Payment.order_id == order.id).first()
        fulfillment = (
            self.db.query(Fulfillment).filter(Fulfillment.order_id == order.id).first()
        )
        refund = self.db.query(Refund).filter(Refund.order_id == order.id).first()
        base = self._to_order_detail(order)

        return AdminOrderDetailResponse(
            **base.model_dump(),
            cancelled_by_user_id=order.cancelled_by_user_id,
            customer_id=customer.id,
            customer_name=customer.name,
            customer_email=customer.email,
            customer_phone=customer.phone,
            payment=PaymentResponse.model_validate(payment) if payment else None,
            fulfillment=FulfillmentResponse.model_validate(fulfillment) if fulfillment else None,
            refund=AdminRefundResponse.model_validate(refund) if refund else None,
        )

    # ------------------------------------------------------------------
    # Cancellation (Phase 18)
    # ------------------------------------------------------------------

    def cancel_own_order(
        self, user_id: int, order_id: int, reason: str | None
    ) -> OrderDetailResponse:
        """Customer self-cancellation - ownership-enforced (404, not 403,
        on another customer's order - this codebase's established
        "don't disclose existence" convention).
        """
        order = self._lock_order_for_cancel(order_id)
        if order.user_id != user_id:
            raise NotFoundError("Order not found.")
        return self._cancel_locked_order(order, actor_user_id=user_id, reason=reason)

    def admin_cancel_order(
        self, admin_user_id: int, order_id: int, reason: str | None
    ) -> OrderDetailResponse:
        """Administrative cancellation - no ownership constraint."""
        order = self._lock_order_for_cancel(order_id)
        return self._cancel_locked_order(
            order, actor_user_id=admin_user_id, reason=reason, is_admin_action=True
        )

    def _lock_order_for_cancel(self, order_id: int) -> Order:
        """Locks Order unconditionally on id, FIRST - this is what lets a
        concurrent cancellation and a concurrent delivery confirmation
        (FulfillmentService.confirm_delivery also locks Order first, see
        its module docstring) resolve to exactly one deterministic winner
        via Postgres's own row lock, rather than a hand-rolled check.
        """
        order = (
            self.db.query(Order).filter(Order.id == order_id).with_for_update().first()
        )
        if order is None:
            raise NotFoundError("Order not found.")
        return order

    def _cancel_locked_order(
        self,
        order: Order,
        *,
        actor_user_id: int,
        reason: str | None,
        is_admin_action: bool = False,
    ) -> OrderDetailResponse:
        """Caller must already hold the order row lock. Central rule: an
        order may be cancelled any time before delivery is completed -
        i.e. from PENDING or CONFIRMED (which covers every Fulfillment
        sub-status: PICKING/PACKED/READY_FOR_DELIVERY/ASSIGNED/
        OUT_FOR_DELIVERY, since the Order itself stays CONFIRMED
        throughout all of those and only becomes COMPLETED at actual
        delivery - see order_state.py). Never legal once COMPLETED,
        EXPIRED, or already CANCELLED.

        One atomic transaction: order status, reservation release, and
        refund-eligibility creation (online-paid orders only) all commit
        together or not at all.
        """
        now = datetime.now(UTC)
        try:
            result = transition_order_status(
                OrderStatus(order.status), OrderStatus.CANCELLED
            )
        except IllegalOrderTransitionError as exc:
            raise ConflictError(
                f"Cannot cancel an order in status {exc.current.value}."
            ) from exc

        if not result.applied:
            # Already CANCELLED - idempotent no-op, nothing left to do.
            self.db.commit()
            return self._to_order_detail(order)

        order.status = OrderStatus.CANCELLED
        order.cancelled_at = now
        order.cancelled_by_user_id = actor_user_id
        order.cancellation_reason = reason

        # Flush BEFORE calling into the reservation service: it internally
        # re-reads this same Order row via `.populate_existing()` (held
        # only for lock ordering - see its own docstring), which would
        # otherwise silently overwrite the four in-memory assignments
        # above with their still-unflushed (pre-cancellation) database
        # values, discarding the cancellation entirely without error.
        self.db.flush()

        # Release the reservation (ACTIVE if never confirmed, COMMITTED if
        # confirmed but not yet delivered - both are valid release sources
        # as of this phase). Physical inventory quantity is untouched -
        # only ever consumed at delivery (FulfillmentService.confirm_delivery).
        InventoryReservationService(self.db).release_reservation_for_order(
            order.id, now=now, reason="order_cancelled"
        )

        # Reverse promotion usage (frees the global/per-customer limit for
        # reuse) - a no-op if this order never redeemed one. The order's
        # own subtotal/discount/total_amount are left untouched: historical
        # pricing must never change once an order exists.
        if order.promotion_id is not None:
            PromotionService(self.db).reverse_redemption_for_order(order.id, now=now)

        # Refund eligibility only for an online payment that actually
        # reached PAID - COD never creates a refund (nothing was
        # collected), and an online payment that never reached PAID has
        # nothing to refund either. Never issues the refund itself - only
        # ADMIN approval + processing ever moves money.
        payment = self.db.query(Payment).filter(Payment.order_id == order.id).first()
        RefundService(self.db).create_refund_if_eligible(order, payment)

        if is_admin_action:
            AdminAuditService(self.db).record(
                admin_user_id=actor_user_id,
                action="order.cancel",
                resource_type="order",
                resource_id=order.id,
                previous_state=result.previous.value,
                new_state=result.current.value,
                reason=reason,
            )

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not cancel order due to a conflicting update."
            ) from exc
        self.db.refresh(order)
        logger.info(
            "ORDER_CANCELLED: order_id=%s actor_user_id=%s reason=%s",
            order.id, actor_user_id, reason,
        )
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
        promo_lines = []
        subtotal_amount = Decimal("0")
        for item in items:
            variant = variants[item.variant_id]
            product = products[variant.product_id]
            price = prices[item.variant_id]
            line_total = (item.quantity * price.price).quantize(
                _CENTS, rounding=ROUND_HALF_UP
            )
            subtotal_amount += line_total
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
            promo_lines.append(
                CartLineForPromo(
                    variant_id=variant.id,
                    product_id=product.id,
                    category_id=product.category_id,
                    quantity=item.quantity,
                    line_total=line_total,
                )
            )

        # Backend-authoritative discount calculation - the same engine the
        # customer-facing preview endpoint uses. The client-supplied
        # `promo_code` is only ever a lookup key here, never a source of
        # the discount amount itself.
        now = datetime.now(UTC)
        promotion_service = PromotionService(self.db)
        evaluation = promotion_service.evaluate_for_cart(
            user_id=user_id, cart_items=promo_lines, promo_code=data.promo_code, now=now
        )
        if data.promo_code and evaluation.code_was_invalid:
            raise BusinessValidationError(evaluation.message)

        total_amount = evaluation.final_total

        order = Order(
            user_id=user_id,
            cart_id=cart.id,
            order_number=self._generate_order_number(),
            status="PENDING",
            subtotal_amount=subtotal_amount,
            discount_amount=evaluation.discount_amount,
            total_amount=total_amount,
            currency=currency,
            promotion_id=evaluation.promotion.id if evaluation.promotion else None,
            applied_promo_code=evaluation.promotion.code if evaluation.promotion else None,
            placed_at=now,
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

        if evaluation.promotion is not None:
            promotion_service.record_redemption(
                promotion_id=evaluation.promotion.id,
                order_id=order.id,
                customer_user_id=user_id,
                discount_amount=evaluation.discount_amount,
                now=now,
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
