"""Customer Management domain service.

A "customer" is not a separate table or a duplicate identity system - it is
an existing `User` row that holds the existing CUSTOMER role (see
app/core/roles.py). Every read here queries `User`/`Address`/`Order`/
`PromotionRedemption` directly; nothing is cached, duplicated, or
recalculated from partial frontend data. Account status
(ACTIVE/INACTIVE/SUSPENDED) is the same `User.status` column
`AuthService.resolve_current_user`/`refresh` already gate every
authenticated request on (app/services/auth.py) - disabling a customer here
takes effect on that customer's very next API call, with zero changes
needed to the auth layer itself.

PERFORMANCE: the list/dashboard queries aggregate order stats via a single
GROUP BY subquery joined once against `users` - never a per-row follow-up
query (no N+1). Expensive lifetime detail (full order/promotion history) is
only ever computed for one customer at a time, on the detail endpoints.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Select, case, func, or_
from sqlalchemy.orm import Session

from app.core.roles import CUSTOMER
from app.core.security import (
    generate_verification_code,
    hash_verification_code,
    normalize_email,
    normalize_phone,
)
from app.exceptions.base import BusinessValidationError, ConflictError, NotFoundError
from app.models.address import Address
from app.models.auth_session import AuthSession
from app.models.bulk_customer_profile import BulkCustomerProfile
from app.models.contact_change_request import ContactChangeRequest
from app.models.customer_note import CustomerNote
from app.models.order import Order
from app.models.promotion import Promotion
from app.models.promotion_redemption import PromotionRedemption
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.address import AddressResponse
from app.schemas.admin_customer import (
    AdminCustomerDetailResponse,
    AdminCustomerListItemResponse,
    AdminCustomerListResponse,
    ConfirmContactChangeRequest,
    CreateCustomerNoteRequest,
    CustomerNoteListResponse,
    CustomerNoteResponse,
    CustomerOrderSummaryResponse,
    CustomerPromotionRedemptionListResponse,
    CustomerPromotionRedemptionRowResponse,
    CustomersDashboardResponse,
    CustomerTimelineEventResponse,
    CustomerTimelineResponse,
    PendingContactChangeResponse,
    RequestContactChangeRequest,
    UpdateCustomerNoteRequest,
    CUSTOMER_ACCOUNT_STATUSES,
)
from app.services.admin_audit import AdminAuditService
from app.services.notification_gateway import ConsoleNotificationGateway, NotificationGateway

# UI-display heuristic only (mirrors Inventory's LOW_STOCK_THRESHOLD
# convention) - "new"/"recently active"/"inactive" are a documented display
# window, never a stored business rule or eligibility condition.
ACTIVITY_WINDOW_DAYS = 30

# Real security parameters (not a display heuristic): how long a
# verification code stays valid and how many wrong guesses are tolerated
# before the request must be re-issued.
CONTACT_CHANGE_CODE_TTL_MINUTES = 15
CONTACT_CHANGE_MAX_ATTEMPTS = 5

_CENTS = Decimal("0.01")

_ORDER_SORT_FIELDS = {"name", "created_at", "last_order_at", "order_count", "total_spend", "average_order_value"}


def _mask_phone(phone: str) -> str:
    """`+91XXXXXXXXXX` -> `+91******7890` - keep the country code and last
    4 digits, mask the rest. Applied whenever the caller lacks
    `customers.view_sensitive`."""
    if len(phone) <= 6:
        return "*" * len(phone)
    visible_prefix = phone[:3] if phone.startswith("+") else phone[:0]
    last4 = phone[-4:]
    masked_len = max(len(phone) - len(visible_prefix) - 4, 4)
    return f"{visible_prefix}{'*' * masked_len}{last4}"


@dataclass(frozen=True)
class _CustomerListFilters:
    q: str | None = None
    account_status: str | None = None
    activity: str | None = None
    has_orders: bool | None = None
    registered_from: datetime | None = None
    registered_to: datetime | None = None
    last_order_from: datetime | None = None
    last_order_to: datetime | None = None


class CustomerService:
    def __init__(self, db: Session, notification_gateway: NotificationGateway | None = None) -> None:
        self.db = db
        # Only the contact-change methods use this - defaulted so every
        # other route (read endpoints, notes, status changes) can keep
        # constructing CustomerService(db) exactly as before.
        self._notification_gateway = notification_gateway or ConsoleNotificationGateway()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _customer_role_subquery(self) -> Select:
        return (
            self.db.query(UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .filter(Role.name == CUSTOMER)
            .subquery()
        )

    def _order_stats_subquery(self):
        completed_amount = case((Order.status == "COMPLETED", Order.total_amount), else_=0)
        completed_flag = case((Order.status == "COMPLETED", 1), else_=0)
        return (
            self.db.query(
                Order.user_id.label("user_id"),
                func.count(Order.id).label("order_count"),
                func.sum(completed_flag).label("completed_order_count"),
                func.coalesce(func.sum(completed_amount), 0).label("total_spend"),
                func.max(Order.placed_at).label("last_order_at"),
                func.min(Order.placed_at).label("first_order_at"),
            )
            .group_by(Order.user_id)
            .subquery()
        )

    def _is_customer(self, user_id: int) -> bool:
        return (
            self.db.query(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .filter(UserRole.user_id == user_id, Role.name == CUSTOMER)
            .first()
            is not None
        )

    def get_customer_or_404(self, user_id: int) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not self._is_customer(user.id):
            raise NotFoundError("Customer not found.")
        return user

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def admin_dashboard(self) -> CustomersDashboardResponse:
        customer_ids = self._customer_role_subquery()
        stats = self._order_stats_subquery()

        total_customers = (
            self.db.query(func.count()).select_from(customer_ids).scalar() or 0
        )

        status_rows = (
            self.db.query(User.status, func.count(User.id))
            .join(customer_ids, customer_ids.c.user_id == User.id)
            .group_by(User.status)
            .all()
        )
        status_counts = dict(status_rows)

        cutoff = datetime.now(UTC) - timedelta(days=ACTIVITY_WINDOW_DAYS)
        new_customers = (
            self.db.query(func.count(User.id))
            .join(customer_ids, customer_ids.c.user_id == User.id)
            .filter(User.created_at >= cutoff)
            .scalar()
            or 0
        )

        with_orders = (
            self.db.query(func.count())
            .select_from(customer_ids)
            .join(stats, stats.c.user_id == customer_ids.c.user_id)
            .scalar()
            or 0
        )
        returning = (
            self.db.query(func.count())
            .select_from(customer_ids)
            .join(stats, stats.c.user_id == customer_ids.c.user_id)
            .filter(stats.c.completed_order_count >= 2)
            .scalar()
            or 0
        )
        revenue_row = (
            self.db.query(
                func.coalesce(func.sum(stats.c.total_spend), 0),
                func.coalesce(func.sum(stats.c.completed_order_count), 0),
            )
            .select_from(customer_ids)
            .join(stats, stats.c.user_id == customer_ids.c.user_id)
            .first()
        )
        total_revenue, total_completed = revenue_row if revenue_row else (Decimal("0"), 0)
        avg_order_value = (
            (Decimal(total_revenue) / total_completed).quantize(_CENTS, rounding=ROUND_HALF_UP)
            if total_completed
            else None
        )

        return CustomersDashboardResponse(
            total_customers=total_customers,
            active_customers=status_counts.get("ACTIVE", 0),
            inactive_customers=status_counts.get("INACTIVE", 0),
            suspended_customers=status_counts.get("SUSPENDED", 0),
            new_customers_last_30_days=new_customers,
            customers_with_orders=with_orders,
            customers_with_no_orders=total_customers - with_orders,
            returning_customers=returning,
            average_order_value=avg_order_value,
            total_realized_revenue=Decimal(total_revenue),
        )

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def admin_list_customers(
        self,
        page: int,
        page_size: int,
        view_sensitive: bool,
        q: str | None = None,
        account_status: str | None = None,
        activity: str | None = None,
        has_orders: bool | None = None,
        registered_from: datetime | None = None,
        registered_to: datetime | None = None,
        last_order_from: datetime | None = None,
        last_order_to: datetime | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> AdminCustomerListResponse:
        customer_ids = self._customer_role_subquery()
        stats = self._order_stats_subquery()
        avg_expr = case(
            (stats.c.completed_order_count > 0, stats.c.total_spend / stats.c.completed_order_count),
            else_=None,
        )

        query = (
            self.db.query(
                User,
                func.coalesce(stats.c.order_count, 0).label("order_count"),
                func.coalesce(stats.c.completed_order_count, 0).label("completed_order_count"),
                func.coalesce(stats.c.total_spend, 0).label("total_spend"),
                avg_expr.label("average_order_value"),
                stats.c.last_order_at.label("last_order_at"),
            )
            .join(customer_ids, customer_ids.c.user_id == User.id)
            .outerjoin(stats, stats.c.user_id == User.id)
        )

        if q:
            term = q.strip()
            like = f"%{term}%"
            conditions = [User.name.ilike(like), User.email.ilike(like), User.phone.ilike(like)]
            if term.isdigit():
                conditions.append(User.id == int(term))
            query = query.filter(or_(*conditions))

        if account_status:
            query = query.filter(User.status == account_status)

        if has_orders is True:
            query = query.filter(stats.c.order_count.isnot(None))
        elif has_orders is False:
            query = query.filter(stats.c.order_count.is_(None))

        cutoff = datetime.now(UTC) - timedelta(days=ACTIVITY_WINDOW_DAYS)
        if activity == "new":
            query = query.filter(User.created_at >= cutoff)
        elif activity == "returning":
            query = query.filter(func.coalesce(stats.c.completed_order_count, 0) >= 2)
        elif activity == "no_orders":
            query = query.filter(stats.c.order_count.is_(None))
        elif activity == "recently_active":
            query = query.filter(stats.c.last_order_at >= cutoff)
        elif activity == "inactive":
            query = query.filter(or_(stats.c.last_order_at < cutoff, stats.c.last_order_at.is_(None)))

        if registered_from:
            query = query.filter(User.created_at >= registered_from)
        if registered_to:
            query = query.filter(User.created_at <= registered_to)
        if last_order_from:
            query = query.filter(stats.c.last_order_at >= last_order_from)
        if last_order_to:
            query = query.filter(stats.c.last_order_at <= last_order_to)

        total = query.count()

        sort_by = sort_by if sort_by in _ORDER_SORT_FIELDS else "created_at"
        sort_map = {
            "name": User.name,
            "created_at": User.created_at,
            "last_order_at": stats.c.last_order_at,
            "order_count": func.coalesce(stats.c.order_count, 0),
            "total_spend": func.coalesce(stats.c.total_spend, 0),
            "average_order_value": avg_expr,
        }
        sort_col = sort_map[sort_by]
        order_expr = sort_col.desc() if sort_dir == "desc" else sort_col.asc()

        rows = (
            query.order_by(order_expr.nulls_last(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items = [
            AdminCustomerListItemResponse(
                id=user.id,
                name=user.name,
                email=user.email,
                phone=user.phone if view_sensitive else _mask_phone(user.phone),
                account_status=user.status,
                order_count=order_count,
                completed_order_count=completed_order_count,
                total_spend=Decimal(total_spend),
                average_order_value=(
                    Decimal(avg).quantize(_CENTS, rounding=ROUND_HALF_UP) if avg is not None else None
                ),
                last_order_at=last_order_at,
                created_at=user.created_at,
            )
            for user, order_count, completed_order_count, total_spend, avg, last_order_at in rows
        ]
        return AdminCustomerListResponse(items=items, page=page, page_size=page_size, total=total)

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    def admin_get_customer_detail(self, user_id: int, view_sensitive: bool) -> AdminCustomerDetailResponse:
        user = self.get_customer_or_404(user_id)

        roles = sorted(
            name
            for (name,) in self.db.query(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user.id)
            .all()
        )
        is_bulk_customer = (
            self.db.query(BulkCustomerProfile.id).filter(BulkCustomerProfile.user_id == user.id).first()
            is not None
        )

        completed_amount = case((Order.status == "COMPLETED", Order.total_amount), else_=0)
        stats_row = (
            self.db.query(
                func.count(Order.id),
                func.coalesce(func.sum(case((Order.status == "COMPLETED", 1), else_=0)), 0),
                func.coalesce(func.sum(case((Order.status == "CANCELLED", 1), else_=0)), 0),
                func.coalesce(func.sum(case((Order.status == "PENDING", 1), else_=0)), 0),
                func.coalesce(func.sum(completed_amount), 0),
                func.min(Order.placed_at),
                func.max(Order.placed_at),
            )
            .filter(Order.user_id == user.id)
            .first()
        )
        total_orders, completed, cancelled, pending, total_spend, first_at, last_at = stats_row
        avg_order_value = (
            (Decimal(total_spend) / completed).quantize(_CENTS, rounding=ROUND_HALF_UP) if completed else None
        )

        promotion_count = (
            self.db.query(func.count(PromotionRedemption.id))
            .filter(PromotionRedemption.customer_user_id == user.id, PromotionRedemption.status == "APPLIED")
            .scalar()
            or 0
        )

        addresses = (
            self.db.query(Address)
            .filter(Address.user_id == user.id)
            .order_by(Address.is_default.desc(), Address.id.desc())
            .all()
        )

        return AdminCustomerDetailResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone if view_sensitive else _mask_phone(user.phone),
            account_status=user.status,
            roles=roles,
            is_bulk_customer=is_bulk_customer,
            created_at=user.created_at,
            updated_at=user.updated_at,
            pending_email_change=self._pending_contact_change(user.id, "EMAIL"),
            pending_phone_change=self._pending_contact_change(user.id, "PHONE"),
            summary=CustomerOrderSummaryResponse(
                total_orders=total_orders,
                completed_orders=completed,
                cancelled_orders=cancelled,
                pending_orders=pending,
                total_spend=Decimal(total_spend),
                average_order_value=avg_order_value,
                first_order_at=first_at,
                last_order_at=last_at,
                promotion_redemptions_count=promotion_count,
            ),
            addresses=[AddressResponse.model_validate(a) for a in addresses],
        )

    # ------------------------------------------------------------------
    # Promotions (customer-scoped view of PromotionRedemption - never a
    # second discount engine)
    # ------------------------------------------------------------------

    def list_customer_promotion_redemptions(
        self, user_id: int, page: int, page_size: int
    ) -> CustomerPromotionRedemptionListResponse:
        self.get_customer_or_404(user_id)
        query = (
            self.db.query(PromotionRedemption, Promotion.name, Promotion.code, Order.order_number)
            .join(Promotion, Promotion.id == PromotionRedemption.promotion_id)
            .join(Order, Order.id == PromotionRedemption.order_id)
            .filter(PromotionRedemption.customer_user_id == user_id)
        )
        total = query.count()
        rows = (
            query.order_by(PromotionRedemption.redeemed_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = [
            CustomerPromotionRedemptionRowResponse(
                id=r.id,
                promotion_id=r.promotion_id,
                promotion_name=name,
                promotion_code=code,
                order_id=r.order_id,
                order_number=order_number,
                discount_amount=r.discount_amount,
                status=r.status,
                redeemed_at=r.redeemed_at,
            )
            for r, name, code, order_number in rows
        ]
        return CustomerPromotionRedemptionListResponse(items=items, page=page, page_size=page_size, total=total)

    # ------------------------------------------------------------------
    # Addresses (read-only admin view - the customer's own AddressService
    # already owns mutation; Customers never duplicates that CRUD)
    # ------------------------------------------------------------------

    def list_customer_addresses(self, user_id: int) -> list[AddressResponse]:
        self.get_customer_or_404(user_id)
        addresses = (
            self.db.query(Address)
            .filter(Address.user_id == user_id)
            .order_by(Address.is_default.desc(), Address.id.desc())
            .all()
        )
        return [AddressResponse.model_validate(a) for a in addresses]

    # ------------------------------------------------------------------
    # Timeline - real events only, sourced from existing tables' own
    # timestamps. No invented/synthesized events.
    # ------------------------------------------------------------------

    def get_customer_timeline(self, user_id: int) -> CustomerTimelineResponse:
        user = self.get_customer_or_404(user_id)
        events: list[CustomerTimelineEventResponse] = [
            CustomerTimelineEventResponse(
                event_type="ACCOUNT_CREATED",
                occurred_at=user.created_at,
                title="Account created",
                description=None,
                resource_type=None,
                resource_id=None,
            )
        ]

        orders = (
            self.db.query(Order)
            .filter(Order.user_id == user_id)
            .order_by(Order.placed_at.desc())
            .limit(50)
            .all()
        )
        for order in orders:
            events.append(
                CustomerTimelineEventResponse(
                    event_type="ORDER_PLACED",
                    occurred_at=order.placed_at,
                    title=f"Order {order.order_number} placed",
                    description=f"{order.currency} {order.total_amount}",
                    resource_type="order",
                    resource_id=order.id,
                )
            )
            if order.status == "CANCELLED" and order.cancelled_at:
                events.append(
                    CustomerTimelineEventResponse(
                        event_type="ORDER_CANCELLED",
                        occurred_at=order.cancelled_at,
                        title=f"Order {order.order_number} cancelled",
                        description=order.cancellation_reason,
                        resource_type="order",
                        resource_id=order.id,
                    )
                )

        redemptions = (
            self.db.query(PromotionRedemption, Promotion.name, Promotion.code)
            .join(Promotion, Promotion.id == PromotionRedemption.promotion_id)
            .filter(PromotionRedemption.customer_user_id == user_id)
            .order_by(PromotionRedemption.redeemed_at.desc())
            .limit(50)
            .all()
        )
        for redemption, name, code in redemptions:
            events.append(
                CustomerTimelineEventResponse(
                    event_type="PROMOTION_REDEEMED",
                    occurred_at=redemption.redeemed_at,
                    title=f"Promotion redeemed: {name}",
                    description=f"{code or 'automatic'} - discount {redemption.discount_amount}",
                    resource_type="promotion",
                    resource_id=redemption.promotion_id,
                )
            )

        events.sort(key=lambda e: e.occurred_at, reverse=True)
        return CustomerTimelineResponse(items=events[:100])

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    def list_notes(self, user_id: int) -> CustomerNoteListResponse:
        self.get_customer_or_404(user_id)
        rows = (
            self.db.query(CustomerNote, User.name)
            .join(User, User.id == CustomerNote.author_admin_user_id)
            .filter(CustomerNote.user_id == user_id)
            .order_by(CustomerNote.created_at.desc())
            .all()
        )
        return CustomerNoteListResponse(
            items=[
                CustomerNoteResponse(
                    id=note.id,
                    user_id=note.user_id,
                    note=note.note,
                    author_name=author_name,
                    created_at=note.created_at,
                    updated_at=note.updated_at,
                )
                for note, author_name in rows
            ]
        )

    def create_note(
        self, user_id: int, data: CreateCustomerNoteRequest, admin_user_id: int
    ) -> CustomerNoteResponse:
        self.get_customer_or_404(user_id)
        note = CustomerNote(user_id=user_id, author_admin_user_id=admin_user_id, note=data.note)
        self.db.add(note)
        self.db.flush()

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="customer.note_create",
            resource_type="customer",
            resource_id=user_id,
        )
        self.db.commit()
        self.db.refresh(note)
        author_name = self.db.query(User.name).filter(User.id == admin_user_id).scalar() or ""
        return CustomerNoteResponse(
            id=note.id,
            user_id=note.user_id,
            note=note.note,
            author_name=author_name,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )

    def update_note(
        self, note_id: int, data: UpdateCustomerNoteRequest, admin_user_id: int
    ) -> CustomerNoteResponse:
        note = self.db.query(CustomerNote).filter(CustomerNote.id == note_id).first()
        if not note:
            raise NotFoundError("Note not found.")

        # AdminActionLog.previous_state/new_state are String(50) - truncate
        # rather than fail the edit over an audit-column width limit.
        previous_excerpt = note.note[:50]
        note.note = data.note
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="customer.note_update",
            resource_type="customer",
            resource_id=note.user_id,
            previous_state=previous_excerpt,
            new_state=data.note[:50],
        )
        self.db.commit()
        self.db.refresh(note)
        author_name = self.db.query(User.name).filter(User.id == note.author_admin_user_id).scalar() or ""
        return CustomerNoteResponse(
            id=note.id,
            user_id=note.user_id,
            note=note.note,
            author_name=author_name,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )

    # ------------------------------------------------------------------
    # Account status
    # ------------------------------------------------------------------

    def admin_set_account_status(
        self, user_id: int, new_status: str, admin_user_id: int, reason: str | None
    ) -> AdminCustomerDetailResponse:
        if new_status not in CUSTOMER_ACCOUNT_STATUSES:
            raise BusinessValidationError("Invalid account status.")
        if user_id == admin_user_id:
            raise BusinessValidationError("You cannot change your own account status.")

        user = self.get_customer_or_404(user_id)
        previous_status = user.status

        if previous_status != new_status:
            user.status = new_status
            self.db.flush()

            if new_status != "ACTIVE":
                # Defense in depth: AuthService.resolve_current_user/refresh
                # already reject any non-ACTIVE user's very next request
                # regardless of session state, but revoking sessions here
                # too means a still-valid access token can't even attempt
                # one more call before that check runs.
                now = datetime.now(UTC)
                self.db.query(AuthSession).filter(
                    AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
                ).update({"revoked_at": now}, synchronize_session=False)

            AdminAuditService(self.db).record(
                admin_user_id=admin_user_id,
                action="customer.status_change",
                resource_type="customer",
                resource_id=user.id,
                previous_state=previous_status,
                new_state=new_status,
                reason=reason,
            )
            self.db.commit()
            self.db.refresh(user)

        return self.admin_get_customer_detail(user.id, view_sensitive=True)

    # ------------------------------------------------------------------
    # Contact change (verification-backed email/phone edit)
    #
    # Never a raw PATCH of users.email/phone: the new value only lands on
    # the User row once whoever controls it proves that by returning the
    # code sent there. This is what makes it safe for Admin to change a
    # customer's login identity at all - see
    # app/services/notification_gateway.py for why the "send" step is an
    # honestly-labeled dev/console placeholder rather than a real email/SMS
    # integration this backend does not have.
    # ------------------------------------------------------------------

    def _pending_contact_change(self, user_id: int, field: str) -> PendingContactChangeResponse | None:
        row = (
            self.db.query(ContactChangeRequest)
            .filter(
                ContactChangeRequest.user_id == user_id,
                ContactChangeRequest.field == field,
                ContactChangeRequest.status == "PENDING",
            )
            .first()
        )
        if row is None or row.expires_at <= datetime.now(UTC):
            return None
        return PendingContactChangeResponse(
            field=row.field, new_value=row.new_value, expires_at=row.expires_at, attempts=row.attempts
        )

    def request_contact_change(
        self, user_id: int, data: RequestContactChangeRequest, admin_user_id: int
    ) -> PendingContactChangeResponse:
        field = data.field.upper()
        if field not in ("EMAIL", "PHONE"):
            raise BusinessValidationError("field must be EMAIL or PHONE.")
        user = self.get_customer_or_404(user_id)

        try:
            normalized = normalize_email(data.new_value) if field == "EMAIL" else normalize_phone(data.new_value)
        except ValueError as exc:
            raise BusinessValidationError(str(exc)) from exc

        current_value = user.email if field == "EMAIL" else user.phone
        if normalized == current_value:
            raise BusinessValidationError(f"That is already this customer's current {field.lower()}.")

        column = User.email if field == "EMAIL" else User.phone
        taken_by_other = (
            self.db.query(User.id).filter(column == normalized, User.id != user_id).first() is not None
        )
        if taken_by_other:
            raise ConflictError(f"Another account already uses this {field.lower()}.")

        # Superseding an existing pending request for the same field (not
        # stacking) - only one live code per user+field at a time, matching
        # the DB's own partial unique index as a second, defense-in-depth
        # layer beyond just relying on the constraint to reject a second
        # insert.
        existing = (
            self.db.query(ContactChangeRequest)
            .filter(
                ContactChangeRequest.user_id == user_id,
                ContactChangeRequest.field == field,
                ContactChangeRequest.status == "PENDING",
            )
            .first()
        )
        if existing is not None:
            existing.status = "CANCELLED"
            self.db.flush()

        code = generate_verification_code()
        now = datetime.now(UTC)
        request = ContactChangeRequest(
            user_id=user_id,
            field=field,
            new_value=normalized,
            code_hash=hash_verification_code(code),
            status="PENDING",
            requested_by_admin_user_id=admin_user_id,
            expires_at=now + timedelta(minutes=CONTACT_CHANGE_CODE_TTL_MINUTES),
        )
        self.db.add(request)

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="customer.contact_change_requested",
            resource_type="customer",
            resource_id=user_id,
            reason=f"{field} change requested",
        )
        self.db.commit()
        self.db.refresh(request)

        # Sent to the NEW destination - proving control of it is the entire
        # point. A channel mismatch (SMS to an email, say) is impossible
        # here since `field` IS the channel.
        self._notification_gateway.send_verification_code(
            channel=field, destination=normalized, code=code
        )

        return PendingContactChangeResponse(
            field=field, new_value=normalized, expires_at=request.expires_at, attempts=0
        )

    def confirm_contact_change(
        self, user_id: int, data: ConfirmContactChangeRequest, admin_user_id: int
    ) -> AdminCustomerDetailResponse:
        field = data.field.upper()
        user = self.get_customer_or_404(user_id)

        request = (
            self.db.query(ContactChangeRequest)
            .filter(
                ContactChangeRequest.user_id == user_id,
                ContactChangeRequest.field == field,
                ContactChangeRequest.status == "PENDING",
            )
            .with_for_update()
            .first()
        )
        if request is None:
            raise NotFoundError("No pending change request for this field.")

        now = datetime.now(UTC)
        if request.expires_at <= now:
            request.status = "EXPIRED"
            self.db.commit()
            raise BusinessValidationError("This verification code has expired. Request a new change.")

        if request.attempts >= CONTACT_CHANGE_MAX_ATTEMPTS:
            request.status = "EXPIRED"
            self.db.commit()
            raise BusinessValidationError("Too many incorrect attempts. Request a new change.")

        if hash_verification_code(data.code) != request.code_hash:
            request.attempts += 1
            self.db.commit()
            remaining = CONTACT_CHANGE_MAX_ATTEMPTS - request.attempts
            raise BusinessValidationError(f"Incorrect verification code. {remaining} attempt(s) remaining.")

        # Re-check uniqueness at confirmation time too - someone else could
        # have taken this email/phone in the window since the code was
        # requested.
        column = User.email if field == "EMAIL" else User.phone
        taken_by_other = (
            self.db.query(User.id).filter(column == request.new_value, User.id != user_id).first() is not None
        )
        if taken_by_other:
            request.status = "EXPIRED"
            self.db.commit()
            raise ConflictError(f"Another account claimed this {field.lower()} in the meantime.")

        previous_value = user.email if field == "EMAIL" else user.phone
        if field == "EMAIL":
            user.email = request.new_value
        else:
            user.phone = request.new_value
        request.status = "VERIFIED"
        request.verified_at = now

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="customer.email_changed" if field == "EMAIL" else "customer.phone_changed",
            resource_type="customer",
            resource_id=user_id,
            previous_state=previous_value[:50],
            new_state=request.new_value[:50],
        )
        self.db.commit()
        self.db.refresh(user)
        return self.admin_get_customer_detail(user_id, view_sensitive=True)

    def cancel_contact_change(self, user_id: int, field: str, admin_user_id: int) -> None:
        field = field.upper()
        self.get_customer_or_404(user_id)
        request = (
            self.db.query(ContactChangeRequest)
            .filter(
                ContactChangeRequest.user_id == user_id,
                ContactChangeRequest.field == field,
                ContactChangeRequest.status == "PENDING",
            )
            .first()
        )
        if request is None:
            raise NotFoundError("No pending change request for this field.")
        request.status = "CANCELLED"
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="customer.contact_change_cancelled",
            resource_type="customer",
            resource_id=user_id,
            reason=f"{field} change cancelled",
        )
        self.db.commit()
