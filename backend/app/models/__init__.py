"""Domain models package.

Exposes Phase 1 (Identity & Access), Phase 2 (Farm & Traceability),
and Phase 3 (Catalog & Products) SQLAlchemy models so that
Base.metadata contains all table definitions.
"""

from app.models.address import Address
from app.models.batch import Batch
from app.models.category import Category
from app.models.farm import Farm
from app.models.price import Price
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.product_variant import ProductVariant
from app.models.quality_check import QualityCheck
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole

__all__ = [
    "Address",
    "Batch",
    "Category",
    "Farm",
    "Price",
    "Product",
    "ProductImage",
    "ProductVariant",
    "QualityCheck",
    "Role",
    "User",
    "UserRole",
]
