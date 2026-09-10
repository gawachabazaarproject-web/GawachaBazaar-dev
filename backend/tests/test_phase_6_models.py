from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.category import Category
from app.models.order import Order
from app.models.order_address import OrderAddress
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.user import User


def _create_user(
    db_session: Session,
    email: str = "customer@example.com",
    phone: str = "+919876543210",
) -> User:
    """Helper to create a user for testing."""
    user = User(
        name="Ramesh Sharma",
        email=email,
        phone=phone,
        password_hash="hashed_pw",
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_category_and_product(
    db_session: Session,
    category_name: str = "Fresh Fruits",
    product_name: str = "Nagpur Oranges",
) -> Product:
    """Helper to create category and product."""
    category = Category(
        name=category_name,
        slug=category_name.lower().replace(" ", "-"),
        status="ACTIVE",
    )
    db_session.add(category)
    db_session.flush()

    product = Product(
        category_id=category.id,
        name=product_name,
        slug=product_name.lower().replace(" ", "-"),
        description="Fresh citrus direct from farm",
        status="ACTIVE",
    )
    db_session.add(product)
    db_session.commit()
    return product


def _create_variant(
    db_session: Session,
    product_id: int,
    name: str = "1kg Bag",
    sku: str = "NAG-ORG-1KG",
    unit: str = "KG",
    quantity: Decimal = Decimal("1.000"),
) -> ProductVariant:
    """Helper to create a product variant."""
    variant = ProductVariant(
        product_id=product_id,
        name=name,
        sku=sku,
        unit=unit,
        quantity=quantity,
        status="ACTIVE",
    )
    db_session.add(variant)
    db_session.commit()
    return variant


def _create_cart(
    db_session: Session,
    user_id: int,
    status: str = "ACTIVE",
) -> Cart:
    """Helper to create a cart."""
    cart = Cart(
        user_id=user_id,
        status=status,
    )
    db_session.add(cart)
    db_session.commit()
    return cart


def _create_cart_item(
    db_session: Session,
    cart_id: int,
    variant_id: int,
    quantity: Decimal = Decimal("2.000"),
) -> CartItem:
    """Helper to create a cart item."""
    item = CartItem(
        cart_id=cart_id,
        variant_id=variant_id,
        quantity=quantity,
    )
    db_session.add(item)
    db_session.commit()
    return item


def _create_order(
    db_session: Session,
    user_id: int,
    order_number: str = "ORD-2026-0001",
    status: str = "PENDING",
    total_amount: Decimal = Decimal("350.00"),
    currency: str = "INR",
    placed_at: datetime | None = None,
    cart_id: int | None = None,
) -> Order:
    """Helper to create an order."""
    if placed_at is None:
        placed_at = datetime.now(UTC)
    order = Order(
        user_id=user_id,
        order_number=order_number,
        status=status,
        total_amount=total_amount,
        currency=currency,
        placed_at=placed_at,
        cart_id=cart_id,
    )
    db_session.add(order)
    db_session.commit()
    return order


def _create_order_item(
    db_session: Session,
    order_id: int,
    variant_id: int,
    product_name: str = "Nagpur Oranges",
    variant_name: str = "1kg Bag",
    sku: str = "NAG-ORG-1KG",
    unit: str = "KG",
    quantity: Decimal = Decimal("2.000"),
    unit_price: Decimal = Decimal("175.00"),
    total_price: Decimal = Decimal("350.00"),
) -> OrderItem:
    """Helper to create an order item."""
    item = OrderItem(
        order_id=order_id,
        variant_id=variant_id,
        product_name=product_name,
        variant_name=variant_name,
        sku=sku,
        unit=unit,
        quantity=quantity,
        unit_price=unit_price,
        total_price=total_price,
    )
    db_session.add(item)
    db_session.commit()
    return item


def _create_order_address(
    db_session: Session,
    order_id: int,
    address_line_1: str = "12 Ramdaspeth",
    address_line_2: str | None = "Flat 302",
    city: str = "Nagpur",
    state: str = "Maharashtra",
    postal_code: str = "440010",
    latitude: Decimal | None = Decimal("21.145800"),
    longitude: Decimal | None = Decimal("79.088200"),
) -> OrderAddress:
    """Helper to create an order address snapshot."""
    address = OrderAddress(
        order_id=order_id,
        address_line_1=address_line_1,
        address_line_2=address_line_2,
        city=city,
        state=state,
        postal_code=postal_code,
        latitude=latitude,
        longitude=longitude,
    )
    db_session.add(address)
    db_session.commit()
    return address


# ============================================================================
# 1. Carts Tests
# ============================================================================


class TestCartModel:
    def test_create_valid_cart(self, db_session: Session) -> None:
        user = _create_user(db_session)
        cart = _create_cart(db_session, user.id, status="ACTIVE")

        assert cart.id is not None
        assert cart.user_id == user.id
        assert cart.status == "ACTIVE"
        assert cart.created_at is not None
        assert cart.updated_at is not None

    def test_single_active_cart_per_user_enforced(self, db_session: Session) -> None:
        user = _create_user(db_session)
        _create_cart(db_session, user.id, status="ACTIVE")

        with pytest.raises(IntegrityError) as exc_info:
            cart2 = Cart(user_id=user.id, status="ACTIVE")
            db_session.add(cart2)
            db_session.commit()
        db_session.rollback()
        assert "uq_carts_user_active" in str(exc_info.value)

    def test_multiple_historical_carts_allowed(self, db_session: Session) -> None:
        user = _create_user(db_session)
        c1 = _create_cart(db_session, user.id, status="CHECKED_OUT")
        c2 = _create_cart(db_session, user.id, status="ABANDONED")
        c3 = _create_cart(db_session, user.id, status="ACTIVE")

        assert c1.id != c2.id != c3.id
        assert c1.status == "CHECKED_OUT"
        assert c2.status == "ABANDONED"
        assert c3.status == "ACTIVE"

    def test_multiple_users_can_have_active_carts(self, db_session: Session) -> None:
        u1 = _create_user(db_session, email="u1@example.com", phone="+919876543201")
        u2 = _create_user(db_session, email="u2@example.com", phone="+919876543202")

        c1 = _create_cart(db_session, u1.id, status="ACTIVE")
        c2 = _create_cart(db_session, u2.id, status="ACTIVE")

        assert c1.user_id == u1.id
        assert c2.user_id == u2.id

    @pytest.mark.parametrize("valid_status", ["ACTIVE", "CHECKED_OUT", "ABANDONED"])
    def test_cart_status_check_constraint_valid(
        self, db_session: Session, valid_status: str
    ) -> None:
        user = _create_user(db_session)
        cart = _create_cart(db_session, user.id, status=valid_status)
        assert cart.status == valid_status

    @pytest.mark.parametrize("invalid_status", ["PENDING", "DRAFT", "CANCELLED", "COMPLETED", ""])
    def test_cart_status_check_constraint_invalid(
        self, db_session: Session, invalid_status: str
    ) -> None:
        user = _create_user(db_session)
        with pytest.raises(IntegrityError) as exc_info:
            cart = Cart(user_id=user.id, status=invalid_status)
            db_session.add(cart)
            db_session.commit()
        db_session.rollback()
        assert "ck_carts_status" in str(exc_info.value)

    def test_cart_user_fk_enforced(self, db_session: Session) -> None:
        with pytest.raises(IntegrityError):
            cart = Cart(user_id=999999, status="ACTIVE")
            db_session.add(cart)
            db_session.commit()
        db_session.rollback()

    def test_delete_user_restricted_with_cart(self, db_session: Session) -> None:
        user = _create_user(db_session)
        _create_cart(db_session, user.id, status="ACTIVE")

        with pytest.raises(IntegrityError):
            db_session.delete(user)
            db_session.commit()
        db_session.rollback()


# ============================================================================
# 2. Cart Items Tests
# ============================================================================


class TestCartItemModel:
    def test_create_valid_cart_item(self, db_session: Session) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)
        cart = _create_cart(db_session, user.id)

        item = _create_cart_item(db_session, cart.id, variant.id, quantity=Decimal("3.500"))
        assert item.id is not None
        assert item.cart_id == cart.id
        assert item.variant_id == variant.id
        assert item.quantity == Decimal("3.500")
        assert item.created_at is not None
        assert item.updated_at is not None

    def test_cart_item_unique_cart_and_variant(self, db_session: Session) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)
        cart = _create_cart(db_session, user.id)

        _create_cart_item(db_session, cart.id, variant.id, quantity=Decimal("1.000"))

        with pytest.raises(IntegrityError) as exc_info:
            duplicate_item = CartItem(
                cart_id=cart.id,
                variant_id=variant.id,
                quantity=Decimal("2.000"),
            )
            db_session.add(duplicate_item)
            db_session.commit()
        db_session.rollback()
        assert "uq_cart_items_cart_id_variant_id" in str(exc_info.value)

    @pytest.mark.parametrize("invalid_qty", [Decimal("0.000"), Decimal("-1.000"), Decimal("-0.001")])
    def test_cart_item_quantity_check_constraint(
        self, db_session: Session, invalid_qty: Decimal
    ) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)
        cart = _create_cart(db_session, user.id)

        with pytest.raises(IntegrityError) as exc_info:
            item = CartItem(
                cart_id=cart.id,
                variant_id=variant.id,
                quantity=invalid_qty,
            )
            db_session.add(item)
            db_session.commit()
        db_session.rollback()
        assert "ck_cart_items_quantity" in str(exc_info.value)

    def test_cart_item_cart_fk_enforced(self, db_session: Session) -> None:
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)

        with pytest.raises(IntegrityError):
            item = CartItem(cart_id=999999, variant_id=variant.id, quantity=Decimal("1.000"))
            db_session.add(item)
            db_session.commit()
        db_session.rollback()

    def test_cart_item_variant_fk_enforced(self, db_session: Session) -> None:
        user = _create_user(db_session)
        cart = _create_cart(db_session, user.id)

        with pytest.raises(IntegrityError):
            item = CartItem(cart_id=cart.id, variant_id=999999, quantity=Decimal("1.000"))
            db_session.add(item)
            db_session.commit()
        db_session.rollback()

    def test_delete_cart_cascades_to_cart_items(self, db_session: Session) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        v1 = _create_variant(db_session, product.id, sku="V1")
        v2 = _create_variant(db_session, product.id, sku="V2")
        cart = _create_cart(db_session, user.id)

        _create_cart_item(db_session, cart.id, v1.id)
        _create_cart_item(db_session, cart.id, v2.id)

        # Count items before delete
        items_count = db_session.execute(
            text("SELECT COUNT(*) FROM cart_items WHERE cart_id = :cid"),
            {"cid": cart.id},
        ).scalar()
        assert items_count == 2

        # Delete cart directly
        db_session.delete(cart)
        db_session.commit()

        # Check items were cascaded
        items_after = db_session.execute(
            text("SELECT COUNT(*) FROM cart_items WHERE cart_id = :cid"),
            {"cid": cart.id},
        ).scalar()
        assert items_after == 0

    def test_delete_variant_restricted_with_cart_items(self, db_session: Session) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)
        cart = _create_cart(db_session, user.id)
        _create_cart_item(db_session, cart.id, variant.id)

        with pytest.raises(IntegrityError):
            db_session.delete(variant)
            db_session.commit()
        db_session.rollback()


# ============================================================================
# 3. Orders Tests
# ============================================================================


class TestOrderModel:
    def test_create_valid_order(self, db_session: Session) -> None:
        user = _create_user(db_session)
        placed = datetime.now(UTC)
        order = _create_order(
            db_session,
            user.id,
            order_number="ORD-2026-0001",
            status="PENDING",
            total_amount=Decimal("499.50"),
            currency="INR",
            placed_at=placed,
        )

        assert order.id is not None
        assert order.user_id == user.id
        assert order.order_number == "ORD-2026-0001"
        assert order.status == "PENDING"
        assert order.total_amount == Decimal("499.50")
        assert order.currency == "INR"
        assert order.placed_at == placed
        assert order.created_at is not None
        assert order.updated_at is not None

    def test_order_number_unique_enforced(self, db_session: Session) -> None:
        user = _create_user(db_session)
        _create_order(db_session, user.id, order_number="ORD-UNIQUE-1")

        with pytest.raises(IntegrityError) as exc_info:
            _create_order(db_session, user.id, order_number="ORD-UNIQUE-1")
        db_session.rollback()
        assert "uq_orders_order_number" in str(exc_info.value)

    @pytest.mark.parametrize("valid_status", ["PENDING", "CONFIRMED", "CANCELLED", "COMPLETED"])
    def test_order_status_check_constraint_valid(
        self, db_session: Session, valid_status: str
    ) -> None:
        user = _create_user(db_session)
        order = _create_order(
            db_session,
            user.id,
            order_number=f"ORD-{valid_status}",
            status=valid_status,
        )
        assert order.status == valid_status

    @pytest.mark.parametrize("invalid_status", ["ACTIVE", "PROCESSING", "SHIPPED", "DELIVERED", ""])
    def test_order_status_check_constraint_invalid(
        self, db_session: Session, invalid_status: str
    ) -> None:
        user = _create_user(db_session)
        with pytest.raises(IntegrityError) as exc_info:
            order = Order(
                user_id=user.id,
                order_number="ORD-INV-STAT",
                status=invalid_status,
                total_amount=Decimal("100.00"),
                currency="INR",
                placed_at=datetime.now(UTC),
            )
            db_session.add(order)
            db_session.commit()
        db_session.rollback()
        assert "ck_orders_status" in str(exc_info.value)

    def test_order_total_amount_zero_allowed(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id, total_amount=Decimal("0.00"))
        assert order.total_amount == Decimal("0.00")

    def test_order_total_amount_negative_fails(self, db_session: Session) -> None:
        user = _create_user(db_session)
        with pytest.raises(IntegrityError) as exc_info:
            order = Order(
                user_id=user.id,
                order_number="ORD-NEG-AMT",
                status="PENDING",
                total_amount=Decimal("-0.01"),
                currency="INR",
                placed_at=datetime.now(UTC),
            )
            db_session.add(order)
            db_session.commit()
        db_session.rollback()
        assert "ck_orders_total_amount" in str(exc_info.value)

    def test_order_user_fk_enforced(self, db_session: Session) -> None:
        with pytest.raises(IntegrityError):
            order = Order(
                user_id=999999,
                order_number="ORD-NO-USER",
                status="PENDING",
                total_amount=Decimal("100.00"),
                currency="INR",
                placed_at=datetime.now(UTC),
            )
            db_session.add(order)
            db_session.commit()
        db_session.rollback()

    def test_delete_user_restricted_with_orders(self, db_session: Session) -> None:
        user = _create_user(db_session)
        _create_order(db_session, user.id)

        with pytest.raises(IntegrityError):
            db_session.delete(user)
            db_session.commit()
        db_session.rollback()

    def test_order_cart_id_nullable_and_references_cart(self, db_session: Session) -> None:
        user = _create_user(db_session)
        cart = _create_cart(db_session, user.id)
        order = _create_order(db_session, user.id, order_number="ORD-CART-1", cart_id=cart.id)

        assert order.cart_id == cart.id
        assert order.cart is not None
        assert order.cart.id == cart.id

    def test_order_without_cart_id_valid(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id, order_number="ORD-NO-CART", cart_id=None)

        assert order.cart_id is None
        assert order.cart is None

    def test_multiple_orders_with_null_cart_id_allowed(self, db_session: Session) -> None:
        user = _create_user(db_session)
        o1 = _create_order(db_session, user.id, order_number="ORD-NULL-1", cart_id=None)
        o2 = _create_order(db_session, user.id, order_number="ORD-NULL-2", cart_id=None)

        assert o1.id is not None
        assert o2.id is not None
        assert o1.cart_id is None
        assert o2.cart_id is None

    def test_order_cart_id_unique_enforced(self, db_session: Session) -> None:
        user = _create_user(db_session)
        cart = _create_cart(db_session, user.id)
        _create_order(db_session, user.id, order_number="ORD-UNIQUE-CART-1", cart_id=cart.id)

        with pytest.raises(IntegrityError) as exc_info:
            _create_order(db_session, user.id, order_number="ORD-UNIQUE-CART-2", cart_id=cart.id)
        db_session.rollback()
        assert "uq_orders_cart_id" in str(exc_info.value)

    def test_order_cart_fk_enforced(self, db_session: Session) -> None:
        user = _create_user(db_session)
        with pytest.raises(IntegrityError):
            order = Order(
                user_id=user.id,
                order_number="ORD-FK-FAIL",
                status="PENDING",
                total_amount=Decimal("100.00"),
                currency="INR",
                placed_at=datetime.now(UTC),
                cart_id=999999,
            )
            db_session.add(order)
            db_session.commit()
        db_session.rollback()

    def test_delete_cart_restricted_with_order(self, db_session: Session) -> None:
        user = _create_user(db_session)
        cart = _create_cart(db_session, user.id)
        _create_order(db_session, user.id, order_number="ORD-DEL-RESTRICT", cart_id=cart.id)

        with pytest.raises(IntegrityError):
            db_session.delete(cart)
            db_session.commit()
        db_session.rollback()

    def test_order_cart_id_schema_invariants(self) -> None:
        assert hasattr(Order, "cart_id")
        mapper = inspect(Order)
        assert mapper.columns["cart_id"].nullable is True


# ============================================================================
# 4. Order Items Tests
# ============================================================================


class TestOrderItemModel:
    def test_create_valid_order_item(self, db_session: Session) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)
        order = _create_order(db_session, user.id)

        item = _create_order_item(
            db_session,
            order_id=order.id,
            variant_id=variant.id,
            product_name="Nagpur Organic Oranges",
            variant_name="1kg Eco-Pack",
            sku="NAG-ORG-1KG",
            unit="KG",
            quantity=Decimal("2.500"),
            unit_price=Decimal("120.00"),
            total_price=Decimal("300.00"),
        )

        assert item.id is not None
        assert item.order_id == order.id
        assert item.variant_id == variant.id
        assert item.product_name == "Nagpur Organic Oranges"
        assert item.variant_name == "1kg Eco-Pack"
        assert item.sku == "NAG-ORG-1KG"
        assert item.unit == "KG"
        assert item.quantity == Decimal("2.500")
        assert item.unit_price == Decimal("120.00")
        assert item.total_price == Decimal("300.00")
        assert item.created_at is not None

    @pytest.mark.parametrize("invalid_qty", [Decimal("0.000"), Decimal("-1.000")])
    def test_order_item_quantity_check_constraint(
        self, db_session: Session, invalid_qty: Decimal
    ) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)
        order = _create_order(db_session, user.id)

        with pytest.raises(IntegrityError) as exc_info:
            item = OrderItem(
                order_id=order.id,
                variant_id=variant.id,
                product_name="P",
                variant_name="V",
                sku="S",
                unit="KG",
                quantity=invalid_qty,
                unit_price=Decimal("100.00"),
                total_price=Decimal("100.00"),
            )
            db_session.add(item)
            db_session.commit()
        db_session.rollback()
        assert "ck_order_items_quantity" in str(exc_info.value)

    @pytest.mark.parametrize("invalid_price", [Decimal("0.00"), Decimal("-10.00")])
    def test_order_item_unit_price_check_constraint(
        self, db_session: Session, invalid_price: Decimal
    ) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)
        order = _create_order(db_session, user.id)

        with pytest.raises(IntegrityError) as exc_info:
            item = OrderItem(
                order_id=order.id,
                variant_id=variant.id,
                product_name="P",
                variant_name="V",
                sku="S",
                unit="KG",
                quantity=Decimal("1.000"),
                unit_price=invalid_price,
                total_price=Decimal("100.00"),
            )
            db_session.add(item)
            db_session.commit()
        db_session.rollback()
        assert "ck_order_items_unit_price" in str(exc_info.value)

    def test_order_item_total_price_negative_fails(self, db_session: Session) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)
        order = _create_order(db_session, user.id)

        with pytest.raises(IntegrityError) as exc_info:
            item = OrderItem(
                order_id=order.id,
                variant_id=variant.id,
                product_name="P",
                variant_name="V",
                sku="S",
                unit="KG",
                quantity=Decimal("1.000"),
                unit_price=Decimal("100.00"),
                total_price=Decimal("-1.00"),
            )
            db_session.add(item)
            db_session.commit()
        db_session.rollback()
        assert "ck_order_items_total_price" in str(exc_info.value)

    def test_order_item_order_fk_enforced(self, db_session: Session) -> None:
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)

        with pytest.raises(IntegrityError):
            item = OrderItem(
                order_id=999999,
                variant_id=variant.id,
                product_name="P",
                variant_name="V",
                sku="S",
                unit="KG",
                quantity=Decimal("1.000"),
                unit_price=Decimal("10.00"),
                total_price=Decimal("10.00"),
            )
            db_session.add(item)
            db_session.commit()
        db_session.rollback()

    def test_order_item_variant_fk_enforced(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)

        with pytest.raises(IntegrityError):
            item = OrderItem(
                order_id=order.id,
                variant_id=999999,
                product_name="P",
                variant_name="V",
                sku="S",
                unit="KG",
                quantity=Decimal("1.000"),
                unit_price=Decimal("10.00"),
                total_price=Decimal("10.00"),
            )
            db_session.add(item)
            db_session.commit()
        db_session.rollback()

    def test_delete_order_restricted_with_items(self, db_session: Session) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)
        order = _create_order(db_session, user.id)
        _create_order_item(db_session, order.id, variant.id)

        with pytest.raises(IntegrityError):
            db_session.delete(order)
            db_session.commit()
        db_session.rollback()

    def test_delete_variant_restricted_with_order_items(self, db_session: Session) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)
        order = _create_order(db_session, user.id)
        _create_order_item(db_session, order.id, variant.id)

        with pytest.raises(IntegrityError):
            db_session.delete(variant)
            db_session.commit()
        db_session.rollback()

    def test_catalog_variant_update_does_not_affect_order_item_snapshot(
        self, db_session: Session
    ) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id, name="Old Name", sku="OLD-SKU")
        order = _create_order(db_session, user.id)
        item = _create_order_item(
            db_session,
            order.id,
            variant.id,
            product_name="Old Product",
            variant_name="Old Name",
            sku="OLD-SKU",
        )

        # Mutate catalog variant
        variant.name = "New Renamed Variant"
        variant.sku = "NEW-SKU-999"
        db_session.commit()

        # Refresh order item and assert snapshot is untouched
        db_session.refresh(item)
        assert item.variant_name == "Old Name"
        assert item.sku == "OLD-SKU"
        assert item.product_name == "Old Product"

    def test_order_item_schema_invariants(self) -> None:
        """Verify OrderItem has no updated_at and no product_id attribute."""
        assert not hasattr(OrderItem, "updated_at")
        assert not hasattr(OrderItem, "product_id")
        mapper = inspect(OrderItem)
        column_names = [c.name for c in mapper.columns]
        assert "updated_at" not in column_names
        assert "product_id" not in column_names


# ============================================================================
# 5. Order Addresses Tests
# ============================================================================


class TestOrderAddressModel:
    def test_create_valid_order_address(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)

        address = _create_order_address(
            db_session,
            order_id=order.id,
            address_line_1="Plot 45, Civil Lines",
            address_line_2="Near High Court",
            city="Nagpur",
            state="Maharashtra",
            postal_code="440001",
            latitude=Decimal("21.152300"),
            longitude=Decimal("79.081500"),
        )

        assert address.id is not None
        assert address.order_id == order.id
        assert address.address_line_1 == "Plot 45, Civil Lines"
        assert address.address_line_2 == "Near High Court"
        assert address.city == "Nagpur"
        assert address.state == "Maharashtra"
        assert address.postal_code == "440001"
        assert address.latitude == Decimal("21.152300")
        assert address.longitude == Decimal("79.081500")
        assert address.created_at is not None

    def test_order_address_unique_order_id_enforced(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        _create_order_address(db_session, order.id)

        with pytest.raises(IntegrityError) as exc_info:
            addr2 = OrderAddress(
                order_id=order.id,
                address_line_1="Second Address",
                city="Nagpur",
                state="Maharashtra",
                postal_code="440001",
            )
            db_session.add(addr2)
            db_session.commit()
        db_session.rollback()
        assert "uq_order_addresses_order_id" in str(exc_info.value)

    def test_order_address_order_fk_enforced(self, db_session: Session) -> None:
        with pytest.raises(IntegrityError):
            addr = OrderAddress(
                order_id=999999,
                address_line_1="Nowhere",
                city="Nagpur",
                state="Maharashtra",
                postal_code="440001",
            )
            db_session.add(addr)
            db_session.commit()
        db_session.rollback()

    def test_delete_order_restricted_with_address(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        _create_order_address(db_session, order.id)

        with pytest.raises(IntegrityError):
            db_session.delete(order)
            db_session.commit()
        db_session.rollback()

    def test_order_address_schema_invariants(self) -> None:
        """Verify OrderAddress has no user_id and no updated_at attribute."""
        assert not hasattr(OrderAddress, "user_id")
        assert not hasattr(OrderAddress, "updated_at")
        mapper = inspect(OrderAddress)
        column_names = [c.name for c in mapper.columns]
        assert "user_id" not in column_names
        assert "updated_at" not in column_names

    def test_order_addresses_redundant_index_not_in_model(self) -> None:
        """Verify redundant index ix_order_addresses_order_id was removed from model."""
        index_names = [idx.name for idx in OrderAddress.__table__.indexes]
        assert "ix_order_addresses_order_id" not in index_names
        constraint_names = [c.name for c in OrderAddress.__table__.constraints]
        assert "uq_order_addresses_order_id" in constraint_names


# ============================================================================
# 6. Relationship Navigation Tests
# ============================================================================


class TestRelationshipNavigation:
    def test_user_and_cart_navigation(self, db_session: Session) -> None:
        user = _create_user(db_session)
        c1 = _create_cart(db_session, user.id, status="ACTIVE")
        db_session.refresh(user)

        assert len(user.carts) == 1
        assert user.carts[0].id == c1.id
        assert c1.user.id == user.id

    def test_cart_and_items_navigation(self, db_session: Session) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        v1 = _create_variant(db_session, product.id, sku="SKU-1")
        v2 = _create_variant(db_session, product.id, sku="SKU-2")
        cart = _create_cart(db_session, user.id)

        item1 = _create_cart_item(db_session, cart.id, v1.id, quantity=Decimal("1.000"))
        item2 = _create_cart_item(db_session, cart.id, v2.id, quantity=Decimal("2.000"))
        db_session.refresh(cart)

        assert len(cart.items) == 2
        assert {item.id for item in cart.items} == {item1.id, item2.id}
        assert item1.cart.id == cart.id
        assert item1.variant.id == v1.id

    def test_variant_cart_items_navigation(self, db_session: Session) -> None:
        u1 = _create_user(db_session, email="c1@example.com", phone="+919876543201")
        u2 = _create_user(db_session, email="c2@example.com", phone="+919876543202")
        cart1 = _create_cart(db_session, u1.id)
        cart2 = _create_cart(db_session, u2.id)

        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)

        _create_cart_item(db_session, cart1.id, variant.id)
        _create_cart_item(db_session, cart2.id, variant.id)
        db_session.refresh(variant)

        assert len(variant.cart_items) == 2

    def test_user_and_order_navigation(self, db_session: Session) -> None:
        user = _create_user(db_session)
        o1 = _create_order(db_session, user.id, order_number="ORD-NAV-1")
        o2 = _create_order(db_session, user.id, order_number="ORD-NAV-2")
        db_session.refresh(user)

        assert len(user.orders) == 2
        assert {o.order_number for o in user.orders} == {"ORD-NAV-1", "ORD-NAV-2"}
        assert o1.user.id == user.id
        assert o2.user.id == user.id

    def test_order_items_and_order_navigation(self, db_session: Session) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)
        order = _create_order(db_session, user.id)

        item = _create_order_item(db_session, order.id, variant.id)
        db_session.refresh(order)

        assert len(order.items) == 1
        assert order.items[0].id == item.id
        assert item.order.id == order.id
        assert item.variant.id == variant.id

    def test_variant_order_items_navigation(self, db_session: Session) -> None:
        user = _create_user(db_session)
        product = _create_category_and_product(db_session)
        variant = _create_variant(db_session, product.id)
        o1 = _create_order(db_session, user.id, order_number="ORD-V-1")
        o2 = _create_order(db_session, user.id, order_number="ORD-V-2")

        _create_order_item(db_session, o1.id, variant.id)
        _create_order_item(db_session, o2.id, variant.id)
        db_session.refresh(variant)

        assert len(variant.order_items) == 2

    def test_order_and_order_address_1_to_1_navigation(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        addr = _create_order_address(db_session, order.id)
        db_session.refresh(order)

        assert order.address is not None
        assert order.address.id == addr.id
        assert addr.order.id == order.id

    def test_cart_and_order_navigation(self, db_session: Session) -> None:
        user = _create_user(db_session)
        cart = _create_cart(db_session, user.id)
        order = _create_order(db_session, user.id, cart_id=cart.id)
        db_session.refresh(cart)
        db_session.refresh(order)

        assert len(cart.orders) == 1
        assert cart.orders[0].id == order.id
        assert order.cart is not None
        assert order.cart.id == cart.id

    def test_delete_order_does_not_delete_cart(self, db_session: Session) -> None:
        user = _create_user(db_session)
        cart = _create_cart(db_session, user.id)
        order = _create_order(db_session, user.id, cart_id=cart.id)
        cart_id = cart.id

        db_session.delete(order)
        db_session.commit()

        surviving_cart = db_session.get(Cart, cart_id)
        assert surviving_cart is not None


# ============================================================================
# 7. Database Catalog & PostgreSQL Audits
# ============================================================================


class TestDatabaseCatalogAudit:
    def test_no_postgresql_enums(self, db_session: Session) -> None:
        """Verify no PostgreSQL custom ENUM types were created."""
        result = db_session.execute(
            text(
                "SELECT t.typname FROM pg_type t "
                "JOIN pg_namespace n ON n.oid = t.typnamespace "
                "WHERE t.typtype = 'e' AND n.nspname = 'public';"
            )
        ).fetchall()
        assert len(result) == 0, f"Expected 0 custom ENUMs, found: {result}"

    def test_no_database_triggers(self, db_session: Session) -> None:
        """Verify no database triggers exist on public schema tables."""
        result = db_session.execute(
            text(
                "SELECT tgname, relname FROM pg_trigger tg "
                "JOIN pg_class c ON c.oid = tg.tgrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND NOT tg.tgisinternal;"
            )
        ).fetchall()
        assert len(result) == 0, f"Expected 0 non-internal triggers, found: {result}"

    def test_phase_6_tables_exist_in_catalog(self, db_session: Session) -> None:
        """Verify all 5 Phase 6 tables exist in information_schema."""
        expected_tables = {"carts", "cart_items", "orders", "order_items", "order_addresses"}
        result = db_session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"
            )
        ).fetchall()
        existing_tables = {row[0] for row in result}
        assert expected_tables.issubset(existing_tables)

    def test_order_items_has_no_updated_at_or_product_id_in_db(self, db_session: Session) -> None:
        """Verify DB column catalog directly for order_items."""
        result = db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'order_items' AND table_schema = 'public';"
            )
        ).fetchall()
        columns = {row[0] for row in result}
        assert "updated_at" not in columns
        assert "product_id" not in columns
        assert "order_id" in columns
        assert "variant_id" in columns
        assert "product_name" in columns
        assert "variant_name" in columns
        assert "sku" in columns
        assert "unit" in columns
        assert "quantity" in columns
        assert "unit_price" in columns
        assert "total_price" in columns

    def test_order_addresses_has_no_user_id_in_db(self, db_session: Session) -> None:
        """Verify DB column catalog directly for order_addresses."""
        result = db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'order_addresses' AND table_schema = 'public';"
            )
        ).fetchall()
        columns = {row[0] for row in result}
        assert "user_id" not in columns
        assert "updated_at" not in columns
        assert "order_id" in columns
        assert "address_line_1" in columns
        assert "city" in columns
        assert "state" in columns
        assert "postal_code" in columns

    def test_orders_cart_id_in_db_catalog(self, db_session: Session) -> None:
        """Verify DB column catalog directly for orders.cart_id."""
        result = db_session.execute(
            text(
                "SELECT column_name, is_nullable FROM information_schema.columns "
                "WHERE table_name = 'orders' AND column_name = 'cart_id' AND table_schema = 'public';"
            )
        ).fetchall()
        assert len(result) == 1
        assert result[0][0] == "cart_id"
        assert result[0][1] == "YES"

    def test_orders_cart_id_unique_constraint_in_db(self, db_session: Session) -> None:
        """Verify uq_orders_cart_id unique constraint exists in PostgreSQL catalog."""
        result = db_session.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conname = 'uq_orders_cart_id' AND contype = 'u';"
            )
        ).fetchall()
        assert len(result) == 1

    def test_orders_cart_id_fk_in_db(self, db_session: Session) -> None:
        """Verify fk_orders_cart_id_carts FK with RESTRICT exists in PostgreSQL catalog."""
        result = db_session.execute(
            text(
                "SELECT conname, confdeltype FROM pg_constraint "
                "WHERE conname = 'fk_orders_cart_id_carts' AND contype = 'f';"
            )
        ).fetchall()
        assert len(result) == 1
        assert result[0][1] == "r"

    def test_order_addresses_redundant_index_removed_from_db(self, db_session: Session) -> None:
        """Verify ix_order_addresses_order_id does not exist in PostgreSQL indexes."""
        result = db_session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'order_addresses' AND schemaname = 'public';"
            )
        ).fetchall()
        index_names = {row[0] for row in result}
        assert "ix_order_addresses_order_id" not in index_names
        assert "uq_order_addresses_order_id" in index_names

    def test_order_addresses_unique_constraint_remains_in_db(self, db_session: Session) -> None:
        """Verify uq_order_addresses_order_id unique constraint exists in PostgreSQL catalog."""
        result = db_session.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conname = 'uq_order_addresses_order_id' AND contype = 'u';"
            )
        ).fetchall()
        assert len(result) == 1
