from app.schemas.base import BaseSchema
from app.schemas.catalog import ProductSummaryResponse


class WishlistResponse(BaseSchema):
    items: list[ProductSummaryResponse]
    product_ids: list[int]
