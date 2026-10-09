from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.exceptions.base import NotFoundError
from app.models.product import Product
from app.models.wishlist_item import WishlistItem
from app.schemas.wishlist import WishlistResponse
from app.services.catalog import CatalogService


class WishlistService:
    def __init__(self, db: Session):
        self.db = db

    def list_items(self, user_id: int) -> WishlistResponse:
        rows = (
            self.db.query(WishlistItem)
            .filter(WishlistItem.user_id == user_id)
            .order_by(WishlistItem.created_at.desc(), WishlistItem.id.desc())
            .all()
        )
        order = [r.product_id for r in rows]
        products = (
            self.db.query(Product)
            .filter(Product.id.in_(order), Product.status == "ACTIVE")
            .options(selectinload(Product.images), selectinload(Product.variants))
            .all()
        )
        by_id = {p.id: p for p in products}
        ordered = [by_id[i] for i in order if i in by_id]
        items = CatalogService(self.db).build_product_summaries(ordered)
        return WishlistResponse(items=items, product_ids=[p.id for p in ordered])

    def add(self, user_id: int, product_id: int) -> None:
        if not self.db.query(Product.id).filter(Product.id == product_id).first():
            raise NotFoundError("Product not found.")
        try:
            self.db.add(WishlistItem(user_id=user_id, product_id=product_id))
            self.db.commit()
        except IntegrityError:
            self.db.rollback()  # already wishlisted - idempotent

    def remove(self, user_id: int, product_id: int) -> None:
        self.db.query(WishlistItem).filter(
            WishlistItem.user_id == user_id, WishlistItem.product_id == product_id
        ).delete()
        self.db.commit()
