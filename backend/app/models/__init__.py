"""Domain models package.

Exposes Phase 1 (Identity & Access), Phase 2 (Farm & Traceability),
Phase 3 (Catalog & Products), Phase 4 (Inventory & Stock), and
Phase 5 (Packaging & Labeling) SQLAlchemy models so that Base.metadata
contains all table definitions.
"""

from app.models.address import Address
from app.models.batch import Batch
from app.models.category import Category
from app.models.farm import Farm
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.packaging_input import PackagingInput
from app.models.packaging_operation import PackagingOperation
from app.models.packaging_output import PackagingOutput
from app.models.price import Price
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.product_variant import ProductVariant
from app.models.quality_check import QualityCheck
from app.models.role import Role
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.models.user_role import UserRole

__all__ = [
    "Address",
    "Batch",
    "Category",
    "Farm",
    "InventoryLocation",
    "InventoryLot",
    "PackagingInput",
    "PackagingOperation",
    "PackagingOutput",
    "Price",
    "Product",
    "ProductImage",
    "ProductVariant",
    "QualityCheck",
    "Role",
    "StockMovement",
    "User",
    "UserRole",
]
