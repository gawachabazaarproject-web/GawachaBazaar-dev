"""Cart domain service: active-cart lifecycle, item management, read-time pricing.

TRANSACTION DESIGN: same rule as Inventory/Packaging (see those modules'
docstrings) - every route here is protected by `require_roles`, which
composes `get_current_user` and therefore always autobegins the session's
transaction via its own reads before any service method runs. No method
here calls `db.begin()`; mutations lock the cart row directly against the
already-open transaction and commit once.

CART CONCURRENCY: every mutating method locks the cart row
(`SELECT ... FOR UPDATE`) as its first real step, via `_get_locked_active_cart`.
This is what makes checkout's own cart-row lock (app/services/order.py)
effective in both directions: a mutation that started before checkout began
will block on the same row, then see `status == CHECKED_OUT` once unblocked
and reject cleanly (409), rather than silently applying a stale change
after the order was already created. Locking the cart row first also means
two concurrent mutations against the SAME cart are fully serialized by
Postgres, so no separate retry-on-conflict logic is needed for
`cart_items` - only the very first cart-creation race (before any row
exists to lock) needs that handling.
"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions.base import ConflictError, NotFoundError
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.schemas.cart import (
    AddCartItemRequest,
    CartItemResponse,
    CartResponse,
    UpdateCartItemRequest,
)
from app.services.pricing import get_current_prices_for_variants

_ACTIVE = "ACTIVE"
_CENTS = Decimal("0.01")


class CartService:
    """Cart/CartItem business logic and read-time price display."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_cart(self, user_id: int) -> CartResponse:
        """Read-only. Never creates a cart as a side effect."""
        cart = (
            self.db.query(Cart)
            .filter(Cart.user_id == user_id, Cart.status == _ACTIVE)
            .first()
        )
        if not cart:
            return CartResponse(
                id=None, status=_ACTIVE, items=[], total_amount=None, currency=None
            )
        items = (
            self.db.query(CartItem)
            .filter(CartItem.cart_id == cart.id)
            .order_by(CartItem.id)
            .all()
        )
        return self._to_cart_response(cart, items)

    def create_cart(self, user_id: int) -> CartResponse:
        cart = self._get_or_create_active_cart(user_id)
        items = (
            self.db.query(CartItem)
            .filter(CartItem.cart_id == cart.id)
            .order_by(CartItem.id)
            .all()
        )
        return self._to_cart_response(cart, items)

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    def add_item(self, user_id: int, data: AddCartItemRequest) -> CartItemResponse:
        self._validate_variant_purchasable(data.variant_id)
        self._get_or_create_active_cart(user_id)
        cart = self._get_locked_active_cart(user_id)

        existing = (
            self.db.query(CartItem)
            .filter(
                CartItem.cart_id == cart.id, CartItem.variant_id == data.variant_id
            )
            .first()
        )
        if existing:
            existing.quantity = existing.quantity + data.quantity
            item = existing
        else:
            item = CartItem(
                cart_id=cart.id, variant_id=data.variant_id, quantity=data.quantity
            )
            self.db.add(item)

        self.db.commit()
        self.db.refresh(item)
        return self._to_item_response(item)

    def update_item_quantity(
        self, user_id: int, item_id: int, data: UpdateCartItemRequest
    ) -> CartItemResponse:
        cart = self._get_locked_active_cart(user_id)
        item = (
            self.db.query(CartItem)
            .filter(CartItem.id == item_id, CartItem.cart_id == cart.id)
            .first()
        )
        if not item:
            raise NotFoundError("Cart item not found.")

        item.quantity = data.quantity
        self.db.commit()
        self.db.refresh(item)
        return self._to_item_response(item)

    def remove_item(self, user_id: int, item_id: int) -> None:
        cart = self._get_locked_active_cart(user_id)
        item = (
            self.db.query(CartItem)
            .filter(CartItem.id == item_id, CartItem.cart_id == cart.id)
            .first()
        )
        if not item:
            raise NotFoundError("Cart item not found.")

        self.db.delete(item)
        self.db.commit()

    def clear_cart(self, user_id: int) -> None:
        cart = self._get_locked_active_cart(user_id)
        self.db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
        self.db.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_active_cart(self, user_id: int) -> Cart:
        """Get-or-create, self-healing the race on the partial unique index.

        Only the first-ever cart creation needs this retry - once a row
        exists, every mutation locks it (`_get_locked_active_cart`) and
        Postgres fully serializes further access.
        """
        cart = (
            self.db.query(Cart)
            .filter(Cart.user_id == user_id, Cart.status == _ACTIVE)
            .first()
        )
        if cart:
            return cart

        cart = Cart(user_id=user_id, status=_ACTIVE)
        self.db.add(cart)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            cart = (
                self.db.query(Cart)
                .filter(Cart.user_id == user_id, Cart.status == _ACTIVE)
                .first()
            )
            if not cart:
                raise
        self.db.refresh(cart)
        return cart

    def _get_locked_active_cart(self, user_id: int) -> Cart:
        """Lock the user's most recent cart row and verify it is ACTIVE.

        Locks the most recent cart for this user without filtering by
        status in the WHERE clause. Filtering by status here would let this
        query silently return no rows once a concurrent checkout commits
        (PostgreSQL excludes a FOR UPDATE row from the result if it no
        longer matches the WHERE clause once the lock is granted) - see
        OrderService.checkout for the same reasoning applied there.
        """
        cart = (
            self.db.query(Cart)
            .filter(Cart.user_id == user_id)
            .order_by(Cart.id.desc())
            .with_for_update()
            .first()
        )
        if not cart:
            raise NotFoundError("No cart found.")
        if cart.status != _ACTIVE:
            raise ConflictError(
                "Your cart is no longer active. It may have just been checked out."
            )
        return cart

    def _validate_variant_purchasable(self, variant_id: int) -> ProductVariant:
        variant = (
            self.db.query(ProductVariant)
            .filter(ProductVariant.id == variant_id)
            .first()
        )
        if not variant:
            raise NotFoundError("Product variant not found.")
        if variant.status != _ACTIVE:
            raise ConflictError("This product variant is not currently available.")

        product = (
            self.db.query(Product).filter(Product.id == variant.product_id).first()
        )
        if not product or product.status != _ACTIVE:
            raise ConflictError("This product is not currently available.")
        return variant

    @staticmethod
    def _line_total(quantity: Decimal, unit_price: Decimal) -> Decimal:
        """Quantize to 2dp - plain Decimal multiplication doesn't round
        (e.g. 2.000 * 50.00 == 100.00000), and this is a display value with
        no DB column/CHECK constraint to catch an unrounded result.
        """
        return (quantity * unit_price).quantize(_CENTS, rounding=ROUND_HALF_UP)

    def _to_item_response(self, item: CartItem) -> CartItemResponse:
        variant = (
            self.db.query(ProductVariant)
            .filter(ProductVariant.id == item.variant_id)
            .first()
        )
        product = (
            self.db.query(Product).filter(Product.id == variant.product_id).first()
        )
        price = get_current_prices_for_variants(self.db, [item.variant_id]).get(
            item.variant_id
        )
        return CartItemResponse(
            id=item.id,
            variant_id=item.variant_id,
            product_name=product.name,
            variant_name=variant.name,
            sku=variant.sku,
            quantity=item.quantity,
            unit_price=price.price if price else None,
            line_total=self._line_total(item.quantity, price.price) if price else None,
            currency=price.currency if price else None,
        )

    def _to_cart_response(self, cart: Cart, items: list[CartItem]) -> CartResponse:
        if not items:
            return CartResponse(
                id=cart.id,
                status=cart.status,
                items=[],
                total_amount=None,
                currency=None,
            )

        variant_ids = [i.variant_id for i in items]
        variants = {
            v.id: v
            for v in self.db.query(ProductVariant)
            .filter(ProductVariant.id.in_(variant_ids))
            .all()
        }
        product_ids = {v.product_id for v in variants.values()}
        products = {
            p.id: p
            for p in self.db.query(Product).filter(Product.id.in_(product_ids)).all()
        }
        prices = get_current_prices_for_variants(self.db, variant_ids)

        item_responses: list[CartItemResponse] = []
        total = Decimal("0")
        currency: str | None = None
        for item in items:
            variant = variants[item.variant_id]
            product = products[variant.product_id]
            price = prices.get(item.variant_id)
            line_total = self._line_total(item.quantity, price.price) if price else None
            if price:
                total += line_total
                if currency is None:
                    currency = price.currency
            item_responses.append(
                CartItemResponse(
                    id=item.id,
                    variant_id=item.variant_id,
                    product_name=product.name,
                    variant_name=variant.name,
                    sku=variant.sku,
                    quantity=item.quantity,
                    unit_price=price.price if price else None,
                    line_total=line_total,
                    currency=price.currency if price else None,
                )
            )

        return CartResponse(
            id=cart.id,
            status=cart.status,
            items=item_responses,
            total_amount=total if currency else None,
            currency=currency,
        )
