"""Domain models package.

Exposes Phase 1 (Identity & Access), Phase 2 (Farm & Traceability),
Phase 3 (Catalog & Products), Phase 4 (Inventory & Stock),
Phase 5 (Packaging & Labeling), Phase 6 (Cart & Orders),
Phase 7 (Payments), Phase 15 (Inventory Reservation & Fulfillment),
Phase 16 (Fulfillment & Delivery Operations), and Phase 17 (Supplier
Management + Bulk & Custom Commerce) SQLAlchemy models so that
Base.metadata contains all table definitions.
"""

from app.models.address import Address
from app.models.auth_session import AuthSession
from app.models.batch import Batch
from app.models.bulk_customer_profile import BulkCustomerProfile
from app.models.bulk_order_request import BulkOrderRequest
from app.models.bulk_order_request_item import BulkOrderRequestItem
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.category import Category
from app.models.farm import Farm
from app.models.fulfillment import Fulfillment
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.inventory_reservation import InventoryReservation
from app.models.inventory_reservation_item import InventoryReservationItem
from app.models.order import Order
from app.models.order_address import OrderAddress
from app.models.order_item import OrderItem
from app.models.packaging_input import PackagingInput
from app.models.packaging_operation import PackagingOperation
from app.models.packaging_output import PackagingOutput
from app.models.payment import Payment
from app.models.payment_transaction import PaymentTransaction
from app.models.payment_webhook_event import PaymentWebhookEvent
from app.models.price import Price
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.product_variant import ProductVariant
from app.models.quality_check import QualityCheck
from app.models.quote import Quote
from app.models.quote_item import QuoteItem
from app.models.quote_version import QuoteVersion
from app.models.role import Role
from app.models.stock_movement import StockMovement
from app.models.supplier import Supplier
from app.models.supplier_evaluation import SupplierEvaluation
from app.models.supplier_product import SupplierProduct
from app.models.user import User
from app.models.user_role import UserRole

__all__ = [
    "Address",
    "AuthSession",
    "Batch",
    "BulkCustomerProfile",
    "BulkOrderRequest",
    "BulkOrderRequestItem",
    "Cart",
    "CartItem",
    "Category",
    "Farm",
    "Fulfillment",
    "InventoryLocation",
    "InventoryLot",
    "InventoryReservation",
    "InventoryReservationItem",
    "Order",
    "OrderAddress",
    "OrderItem",
    "PackagingInput",
    "PackagingOperation",
    "PackagingOutput",
    "Payment",
    "PaymentTransaction",
    "PaymentWebhookEvent",
    "Price",
    "Product",
    "ProductImage",
    "ProductVariant",
    "QualityCheck",
    "Quote",
    "QuoteItem",
    "QuoteVersion",
    "Role",
    "StockMovement",
    "Supplier",
    "SupplierEvaluation",
    "SupplierProduct",
    "User",
    "UserRole",
]
