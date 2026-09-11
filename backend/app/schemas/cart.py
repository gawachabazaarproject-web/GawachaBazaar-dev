"""Cart domain schemas."""

from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class AddCartItemRequest(BaseSchema):
    variant_id: int
    quantity: Decimal = Field(..., gt=0, max_digits=12, decimal_places=3)


class UpdateCartItemRequest(BaseSchema):
    quantity: Decimal = Field(..., gt=0, max_digits=12, decimal_places=3)


class CartItemResponse(BaseSchema):
    id: int
    variant_id: int
    product_name: str
    variant_name: str
    sku: str
    quantity: Decimal
    # Resolved dynamically at read time (never stored on cart_items). Null
    # when the variant currently has no applicable price - the cart can
    # still be viewed/edited; checkout is where an unpriced item hard-fails.
    unit_price: Decimal | None = None
    line_total: Decimal | None = None
    currency: str | None = None


class CartResponse(BaseSchema):
    # Null when the user has no active cart yet - GET /cart never creates
    # one as a side effect.
    id: int | None
    status: str
    items: list[CartItemResponse]
    # Sum of only the items that currently have a resolvable price. Null
    # currency indicates either no items, no priced items, or mixed
    # currencies among priced items (display-only; checkout enforces a
    # single currency strictly).
    total_amount: Decimal | None = None
    currency: str | None = None
