from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_transaction import PaymentTransaction
from app.models.user import User


def _create_user(
    db_session: Session,
    email: str = "payer@example.com",
    phone: str = "+919876543299",
) -> User:
    """Helper to create a user for testing."""
    user = User(
        name="Vikram Deshmukh",
        email=email,
        phone=phone,
        password_hash="hashed_pw",
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_order(
    db_session: Session,
    user_id: int,
    order_number: str = "ORD-2026-PAY-001",
    total_amount: Decimal = Decimal("850.00"),
) -> Order:
    """Helper to create an order for testing."""
    order = Order(
        user_id=user_id,
        order_number=order_number,
        status="PENDING",
        total_amount=total_amount,
        currency="INR",
        placed_at=datetime.now(UTC),
    )
    db_session.add(order)
    db_session.commit()
    return order


def _create_payment(
    db_session: Session,
    order_id: int,
    payment_method: str = "UPI",
    status: str = "PENDING",
    amount: Decimal = Decimal("850.00"),
    currency: str = "INR",
    paid_at: datetime | None = None,
) -> Payment:
    """Helper to create a payment for testing."""
    payment = Payment(
        order_id=order_id,
        payment_method=payment_method,
        status=status,
        amount=amount,
        currency=currency,
        paid_at=paid_at,
    )
    db_session.add(payment)
    db_session.commit()
    return payment


def _create_transaction(
    db_session: Session,
    payment_id: int,
    transaction_type: str = "PAYMENT",
    status: str = "INITIATED",
    amount: Decimal = Decimal("850.00"),
    currency: str = "INR",
    gateway_name: str | None = None,
    gateway_transaction_id: str | None = None,
    idempotency_key: str | None = None,
    gateway_response: str | None = None,
    failure_reason: str | None = None,
    initiated_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> PaymentTransaction:
    """Helper to create a payment transaction for testing."""
    if initiated_at is None:
        initiated_at = datetime.now(UTC)
    txn = PaymentTransaction(
        payment_id=payment_id,
        transaction_type=transaction_type,
        status=status,
        amount=amount,
        currency=currency,
        gateway_name=gateway_name,
        gateway_transaction_id=gateway_transaction_id,
        idempotency_key=idempotency_key,
        gateway_response=gateway_response,
        failure_reason=failure_reason,
        initiated_at=initiated_at,
        completed_at=completed_at,
    )
    db_session.add(txn)
    db_session.commit()
    return txn


# ============================================================================
# 1. Payments Tests
# ============================================================================


class TestPaymentModel:
    def test_create_valid_payment_upi(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        payment = _create_payment(db_session, order.id, payment_method="UPI", status="PENDING")

        assert payment.id is not None
        assert payment.order_id == order.id
        assert payment.payment_method == "UPI"
        assert payment.status == "PENDING"
        assert payment.amount == Decimal("850.00")
        assert payment.currency == "INR"
        assert payment.paid_at is None
        assert payment.created_at is not None
        assert payment.updated_at is not None

    def test_create_valid_payment_cod(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        payment = _create_payment(db_session, order.id, payment_method="COD", status="PENDING")

        assert payment.payment_method == "COD"
        assert payment.paid_at is None

    def test_payment_paid_at_can_be_set(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        now = datetime.now(UTC)
        payment = _create_payment(
            db_session,
            order.id,
            payment_method="UPI",
            status="PAID",
            paid_at=now,
        )

        assert payment.status == "PAID"
        assert payment.paid_at == now

    def test_single_payment_per_order_enforced(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        _create_payment(db_session, order.id)

        with pytest.raises(IntegrityError) as exc_info:
            duplicate_payment = Payment(
                order_id=order.id,
                payment_method="COD",
                status="PENDING",
                amount=Decimal("850.00"),
                currency="INR",
            )
            db_session.add(duplicate_payment)
            db_session.commit()
        db_session.rollback()
        assert "uq_payments_order_id" in str(exc_info.value)

    @pytest.mark.parametrize("valid_method", ["UPI", "COD"])
    def test_valid_payment_methods_accepted(
        self, db_session: Session, valid_method: str
    ) -> None:
        user = _create_user(db_session, email=f"user_{valid_method}@example.com", phone=f"+9198765432{valid_method[:2].lower()}")
        order = _create_order(db_session, user.id, order_number=f"ORD-METH-{valid_method}")
        payment = _create_payment(db_session, order.id, payment_method=valid_method)
        assert payment.payment_method == valid_method

    @pytest.mark.parametrize("invalid_method", ["CARD", "NETBANKING", "WALLET", "STRIPE", "RAZORPAY", ""])
    def test_invalid_payment_method_rejected(
        self, db_session: Session, invalid_method: str
    ) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        with pytest.raises(IntegrityError) as exc_info:
            payment = Payment(
                order_id=order.id,
                payment_method=invalid_method,
                status="PENDING",
                amount=Decimal("100.00"),
                currency="INR",
            )
            db_session.add(payment)
            db_session.commit()
        db_session.rollback()
        assert "ck_payments_payment_method" in str(exc_info.value)

    @pytest.mark.parametrize("valid_status", ["PENDING", "PROCESSING", "PAID", "FAILED", "CANCELLED", "EXPIRED"])
    def test_valid_payment_statuses_accepted(
        self, db_session: Session, valid_status: str
    ) -> None:
        user = _create_user(db_session, email=f"stat_{valid_status}@example.com", phone=f"+9198765431{valid_status[:2]}")
        order = _create_order(db_session, user.id, order_number=f"ORD-STAT-{valid_status}")
        payment = _create_payment(db_session, order.id, status=valid_status)
        assert payment.status == valid_status

    @pytest.mark.parametrize("invalid_status", ["INITIATED", "SUCCESS", "REFUNDED", "COMPLETED", ""])
    def test_invalid_payment_status_rejected(
        self, db_session: Session, invalid_status: str
    ) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        with pytest.raises(IntegrityError) as exc_info:
            payment = Payment(
                order_id=order.id,
                payment_method="UPI",
                status=invalid_status,
                amount=Decimal("100.00"),
                currency="INR",
            )
            db_session.add(payment)
            db_session.commit()
        db_session.rollback()
        assert "ck_payments_status" in str(exc_info.value)

    @pytest.mark.parametrize("invalid_amt", [Decimal("0.00"), Decimal("-1.00"), Decimal("-0.01")])
    def test_payment_amount_check_constraint_rejects_zero_and_negative(
        self, db_session: Session, invalid_amt: Decimal
    ) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        with pytest.raises(IntegrityError) as exc_info:
            payment = Payment(
                order_id=order.id,
                payment_method="UPI",
                status="PENDING",
                amount=invalid_amt,
                currency="INR",
            )
            db_session.add(payment)
            db_session.commit()
        db_session.rollback()
        assert "ck_payments_amount" in str(exc_info.value)

    def test_payment_order_fk_enforced(self, db_session: Session) -> None:
        with pytest.raises(IntegrityError):
            payment = Payment(
                order_id=999999,
                payment_method="UPI",
                status="PENDING",
                amount=Decimal("100.00"),
                currency="INR",
            )
            db_session.add(payment)
            db_session.commit()
        db_session.rollback()

    def test_delete_order_restricted_with_payment(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        _create_payment(db_session, order.id)

        with pytest.raises(IntegrityError):
            db_session.delete(order)
            db_session.commit()
        db_session.rollback()


# ============================================================================
# 2. Payment Transactions Tests
# ============================================================================


class TestPaymentTransactionModel:
    def test_create_valid_transaction(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        payment = _create_payment(db_session, order.id)

        now = datetime.now(UTC)
        txn = _create_transaction(
            db_session,
            payment_id=payment.id,
            transaction_type="PAYMENT",
            status="INITIATED",
            amount=Decimal("850.00"),
            currency="INR",
            gateway_name="razorpay",
            gateway_transaction_id="pay_K1234567890",
            idempotency_key="idemp_abc_123",
            initiated_at=now,
        )

        assert txn.id is not None
        assert txn.payment_id == payment.id
        assert txn.transaction_type == "PAYMENT"
        assert txn.status == "INITIATED"
        assert txn.amount == Decimal("850.00")
        assert txn.currency == "INR"
        assert txn.gateway_name == "razorpay"
        assert txn.gateway_transaction_id == "pay_K1234567890"
        assert txn.idempotency_key == "idemp_abc_123"
        assert txn.initiated_at == now
        assert txn.completed_at is None
        assert txn.created_at is not None

    def test_multiple_transactions_per_payment_allowed(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        payment = _create_payment(db_session, order.id)

        t1 = _create_transaction(
            db_session,
            payment_id=payment.id,
            status="FAILED",
            gateway_transaction_id="txn_fail_1",
            failure_reason="Bank server down",
            completed_at=datetime.now(UTC),
        )
        t2 = _create_transaction(
            db_session,
            payment_id=payment.id,
            status="FAILED",
            gateway_transaction_id="txn_fail_2",
            failure_reason="Insufficient balance",
            completed_at=datetime.now(UTC),
        )
        t3 = _create_transaction(
            db_session,
            payment_id=payment.id,
            status="SUCCESS",
            gateway_transaction_id="txn_success_3",
            completed_at=datetime.now(UTC),
        )

        assert t1.id != t2.id != t3.id
        db_session.refresh(payment)
        assert len(payment.transactions) == 3

    def test_transaction_type_payment_accepted(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        payment = _create_payment(db_session, order.id)
        txn = _create_transaction(db_session, payment.id, transaction_type="PAYMENT")
        assert txn.transaction_type == "PAYMENT"

    @pytest.mark.parametrize("invalid_type", ["REFUND", "CHARGEBACK", "AUTH", "CAPTURE", ""])
    def test_unsupported_transaction_types_rejected(
        self, db_session: Session, invalid_type: str
    ) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        payment = _create_payment(db_session, order.id)

        with pytest.raises(IntegrityError) as exc_info:
            txn = PaymentTransaction(
                payment_id=payment.id,
                transaction_type=invalid_type,
                status="INITIATED",
                amount=Decimal("100.00"),
                currency="INR",
                initiated_at=datetime.now(UTC),
            )
            db_session.add(txn)
            db_session.commit()
        db_session.rollback()
        assert "ck_payment_transactions_transaction_type" in str(exc_info.value)

    @pytest.mark.parametrize("valid_status", ["INITIATED", "PROCESSING", "SUCCESS", "FAILED", "CANCELLED", "EXPIRED"])
    def test_valid_transaction_statuses_accepted(
        self, db_session: Session, valid_status: str
    ) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        payment = _create_payment(db_session, order.id)
        txn = _create_transaction(db_session, payment.id, status=valid_status)
        assert txn.status == valid_status

    @pytest.mark.parametrize("invalid_status", ["PENDING", "PAID", "COMPLETED", "SETTLED", ""])
    def test_invalid_transaction_status_rejected(
        self, db_session: Session, invalid_status: str
    ) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        payment = _create_payment(db_session, order.id)

        with pytest.raises(IntegrityError) as exc_info:
            txn = PaymentTransaction(
                payment_id=payment.id,
                transaction_type="PAYMENT",
                status=invalid_status,
                amount=Decimal("100.00"),
                currency="INR",
                initiated_at=datetime.now(UTC),
            )
            db_session.add(txn)
            db_session.commit()
        db_session.rollback()
        assert "ck_payment_transactions_status" in str(exc_info.value)

    @pytest.mark.parametrize("invalid_amt", [Decimal("0.00"), Decimal("-1.00")])
    def test_transaction_amount_check_constraint_rejects_zero_and_negative(
        self, db_session: Session, invalid_amt: Decimal
    ) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        payment = _create_payment(db_session, order.id)

        with pytest.raises(IntegrityError) as exc_info:
            txn = PaymentTransaction(
                payment_id=payment.id,
                transaction_type="PAYMENT",
                status="INITIATED",
                amount=invalid_amt,
                currency="INR",
                initiated_at=datetime.now(UTC),
            )
            db_session.add(txn)
            db_session.commit()
        db_session.rollback()
        assert "ck_payment_transactions_amount" in str(exc_info.value)

    def test_idempotency_key_uniqueness_enforced_for_non_null(
        self, db_session: Session
    ) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        payment = _create_payment(db_session, order.id)

        _create_transaction(db_session, payment.id, idempotency_key="unique_idemp_key_1")

        with pytest.raises(IntegrityError) as exc_info:
            _create_transaction(db_session, payment.id, idempotency_key="unique_idemp_key_1")
        db_session.rollback()
        assert "uq_payment_transactions_idempotency_key" in str(exc_info.value)

    def test_multiple_null_idempotency_keys_allowed(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        payment = _create_payment(db_session, order.id)

        t1 = _create_transaction(db_session, payment.id, idempotency_key=None)
        t2 = _create_transaction(db_session, payment.id, idempotency_key=None)
        t3 = _create_transaction(db_session, payment.id, idempotency_key=None)

        assert t1.id != t2.id != t3.id
        assert t1.idempotency_key is None
        assert t2.idempotency_key is None
        assert t3.idempotency_key is None

    def test_transaction_payment_fk_enforced(self, db_session: Session) -> None:
        with pytest.raises(IntegrityError):
            txn = PaymentTransaction(
                payment_id=999999,
                transaction_type="PAYMENT",
                status="INITIATED",
                amount=Decimal("100.00"),
                currency="INR",
                initiated_at=datetime.now(UTC),
            )
            db_session.add(txn)
            db_session.commit()
        db_session.rollback()

    def test_delete_payment_restricted_with_transactions(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        payment = _create_payment(db_session, order.id)
        _create_transaction(db_session, payment.id)

        with pytest.raises(IntegrityError):
            db_session.delete(payment)
            db_session.commit()
        db_session.rollback()

    def test_payment_transaction_has_no_updated_at(self) -> None:
        """Verify PaymentTransaction has no updated_at attribute (append-oriented)."""
        assert not hasattr(PaymentTransaction, "updated_at")
        mapper = inspect(PaymentTransaction)
        column_names = [c.name for c in mapper.columns]
        assert "updated_at" not in column_names


# ============================================================================
# 3. Relationships & Navigation Tests
# ============================================================================


class TestPaymentRelationships:
    def test_order_to_payment_and_back(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        payment = _create_payment(db_session, order.id)

        db_session.refresh(order)
        assert order.payment is not None
        assert order.payment.id == payment.id
        assert payment.order.id == order.id

    def test_payment_to_transactions_and_back(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id)
        payment = _create_payment(db_session, order.id)

        t1 = _create_transaction(db_session, payment.id, status="INITIATED")
        t2 = _create_transaction(db_session, payment.id, status="SUCCESS")

        db_session.refresh(payment)
        assert len(payment.transactions) == 2
        assert {t.id for t in payment.transactions} == {t1.id, t2.id}
        assert t1.payment.id == payment.id
        assert t2.payment.id == payment.id

    def test_user_has_no_direct_payment_relationship(self) -> None:
        """Verify User does not contain a direct payments relationship."""
        assert not hasattr(User, "payments")
        assert not hasattr(User, "payment_transactions")


# ============================================================================
# 4. UPI / COD Data Behavior Tests
# ============================================================================


class TestPaymentMethodBehaviors:
    def test_upi_and_cod_coexistence(self, db_session: Session) -> None:
        u1 = _create_user(db_session, email="upi_user@example.com", phone="+919876543101")
        u2 = _create_user(db_session, email="cod_user@example.com", phone="+919876543102")

        o1 = _create_order(db_session, u1.id, order_number="ORD-UPI-001")
        o2 = _create_order(db_session, u2.id, order_number="ORD-COD-001")

        p_upi = _create_payment(db_session, o1.id, payment_method="UPI", status="PAID")
        p_cod = _create_payment(db_session, o2.id, payment_method="COD", status="PENDING")

        # UPI transaction with gateway info
        t_upi = _create_transaction(
            db_session,
            p_upi.id,
            status="SUCCESS",
            gateway_name="phonepe",
            gateway_transaction_id="T260909001",
            idempotency_key="idemp_upi_1",
        )

        # COD transaction without gateway info
        t_cod = _create_transaction(
            db_session,
            p_cod.id,
            status="INITIATED",
            gateway_name=None,
            gateway_transaction_id=None,
            idempotency_key=None,
        )

        assert t_upi.gateway_name == "phonepe"
        assert t_upi.gateway_transaction_id == "T260909001"
        assert t_cod.gateway_name is None
        assert t_cod.gateway_transaction_id is None
        assert p_upi.payment_method == "UPI"
        assert p_cod.payment_method == "COD"

    def test_payment_amount_is_independent_snapshot(self, db_session: Session) -> None:
        user = _create_user(db_session)
        order = _create_order(db_session, user.id, total_amount=Decimal("500.00"))
        payment = _create_payment(db_session, order.id, amount=Decimal("500.00"))

        # Mutate order total (e.g. post-purchase modification)
        order.total_amount = Decimal("750.00")
        db_session.commit()

        # Payment amount must remain the original snapshot
        db_session.refresh(payment)
        assert payment.amount == Decimal("500.00")


# ============================================================================
# 5. Database Catalog & PostgreSQL Invariants Audit
# ============================================================================


class TestDatabaseCatalogAudit:
    def test_no_postgresql_enums(self, db_session: Session) -> None:
        """Verify no PostgreSQL custom ENUM types exist in the database."""
        result = db_session.execute(
            text(
                "SELECT t.typname FROM pg_type t "
                "JOIN pg_namespace n ON n.oid = t.typnamespace "
                "WHERE t.typtype = 'e' AND n.nspname = 'public';"
            )
        ).fetchall()
        assert len(result) == 0, f"Found unexpected PostgreSQL ENUM types: {result}"

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
        assert len(result) == 0, f"Found unexpected non-internal triggers: {result}"

    def test_phase_7_tables_exist_in_catalog(self, db_session: Session) -> None:
        """Verify payments and payment_transactions exist in information_schema."""
        expected_tables = {"payments", "payment_transactions"}
        result = db_session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"
            )
        ).fetchall()
        existing_tables = {row[0] for row in result}
        assert expected_tables.issubset(existing_tables)

    def test_payment_transactions_has_no_updated_at_in_db(self, db_session: Session) -> None:
        """Verify payment_transactions has no updated_at column in PostgreSQL."""
        result = db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'payment_transactions' AND table_schema = 'public';"
            )
        ).fetchall()
        columns = {row[0] for row in result}
        assert "updated_at" not in columns
        assert "payment_id" in columns
        assert "transaction_type" in columns
        assert "status" in columns
        assert "amount" in columns
        assert "currency" in columns
        assert "initiated_at" in columns
        assert "created_at" in columns
