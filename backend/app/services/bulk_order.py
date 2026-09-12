"""Bulk & custom commerce domain service.

CORE RULE (see ARCHITECTURE.md): a request is never an Order. Nothing in
this file touches `orders`/`payments`/`inventory_reservations` until
`convert_to_order`, which runs at the very end of the pipeline
(REQUESTED -> UNDER_REVIEW -> QUOTED -> CUSTOMER_ACCEPTED ->
CONVERTED_TO_ORDER) and reuses the EXISTING Order/Reservation machinery
verbatim rather than building a parallel one:
  - Order/OrderItem/OrderAddress creation mirrors OrderService.checkout's
    own snapshot pattern exactly (same fields, same rounding).
  - Inventory reservation is created via the unmodified
    InventoryReservationService.create_reservation_for_order - a
    converted bulk order gets the exact same FIFO allocation, oversell
    protection, and 30-minute unpaid-window expiry as a retail order,
    for free.
  - Payment/fulfillment/delivery happen entirely through the existing
    Phase 14/15/16 endpoints afterward - nothing bulk-specific is added
    to those flows.

TRANSACTION DESIGN: same autobegin/no-explicit-begin rule as every other
service in this codebase.

LOCK ORDERING: this domain's own chain is
BulkOrderRequest -> Quote -> QuoteVersion(s). It only intersects the
existing Cart -> Order -> Payment -> Fulfillment -> Reservation ->
InventoryLots chain at the single moment of conversion, where it creates
a brand-new Order (nothing else could be concurrently holding a lock on a
row that doesn't exist yet) and then delegates to
InventoryReservationService's own established lock order unchanged.
`BulkOrderRequest` is always locked first within this domain's own
operations, unconditionally on id (the same retry-safe pattern used
throughout this codebase), so a concurrent accept-vs-requote race
resolves to one winner cleanly rather than a lost update.
"""

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.exceptions.base import BusinessValidationError, ConflictError, NotFoundError
from app.models.address import Address
from app.models.bulk_customer_profile import BulkCustomerProfile
from app.models.bulk_order_request import BulkOrderRequest
from app.models.bulk_order_request_item import BulkOrderRequestItem
from app.models.inventory_lot import InventoryLot
from app.models.order import Order
from app.models.order_address import OrderAddress
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.quote import Quote
from app.models.quote_item import QuoteItem
from app.models.quote_version import QuoteVersion
from app.schemas.bulk_order import (
    AdminBulkOrderRequestListResponse,
    AdminBulkOrderRequestResponse,
    BulkCustomerProfileResponse,
    BulkOrderRequestAddressResponse,
    BulkOrderRequestItemResponse,
    BulkOrderRequestListResponse,
    BulkOrderRequestResponse,
    CreateBulkOrderRequestRequest,
    CreateQuoteVersionRequest,
    QuoteItemResponse,
    QuoteResponse,
    QuoteVersionResponse,
    UpsertBulkCustomerProfileRequest,
    VariantAvailabilityResponse,
)
from app.schemas.order import (
    OrderAddressResponse,
    OrderDetailResponse,
    OrderItemResponse,
    OrderResponse,
)
from app.services.bulk_order_state import (
    BulkOrderRequestStatus,
    IllegalBulkOrderRequestTransitionError,
    transition_bulk_order_request_status,
)
from app.services.inventory_reservation import InventoryReservationService
from app.services.order import OrderService
from app.services.quote_state import (
    IllegalQuoteVersionTransitionError,
    QuoteVersionStatus,
    transition_quote_version_status,
)

_CENTS = Decimal("0.01")
_QUOTABLE_STATUSES = (
    BulkOrderRequestStatus.REQUESTED,
    BulkOrderRequestStatus.UNDER_REVIEW,
    BulkOrderRequestStatus.QUOTED,
)


class BulkOrderService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Bulk customer profile
    # ------------------------------------------------------------------

    def upsert_profile(
        self, user_id: int, data: UpsertBulkCustomerProfileRequest
    ) -> BulkCustomerProfileResponse:
        profile = (
            self.db.query(BulkCustomerProfile)
            .filter(BulkCustomerProfile.user_id == user_id)
            .first()
        )
        if profile is None:
            profile = BulkCustomerProfile(user_id=user_id, **data.model_dump())
            self.db.add(profile)
        else:
            for field, value in data.model_dump().items():
                setattr(profile, field, value)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Could not save bulk customer profile.") from exc
        self.db.refresh(profile)
        return BulkCustomerProfileResponse.model_validate(profile)

    def get_profile_or_404(self, user_id: int) -> BulkCustomerProfileResponse:
        profile = (
            self.db.query(BulkCustomerProfile)
            .filter(BulkCustomerProfile.user_id == user_id)
            .first()
        )
        if profile is None:
            raise NotFoundError("Bulk customer profile not found.")
        return BulkCustomerProfileResponse.model_validate(profile)

    # ------------------------------------------------------------------
    # Requests - customer-facing
    # ------------------------------------------------------------------

    def create_request(
        self, user_id: int, data: CreateBulkOrderRequestRequest
    ) -> BulkOrderRequestResponse:
        if data.address_id is not None:
            address = (
                self.db.query(Address)
                .filter(Address.id == data.address_id, Address.user_id == user_id)
                .first()
            )
            if not address:
                raise NotFoundError("Address not found.")

        product_ids = {item.product_id for item in data.items if item.product_id is not None}
        products = {
            p.id: p
            for p in self.db.query(Product).filter(Product.id.in_(product_ids)).all()
        } if product_ids else {}
        missing = product_ids - products.keys()
        if missing:
            raise NotFoundError(f"Product(s) not found: {sorted(missing)}.")

        request = BulkOrderRequest(
            customer_user_id=user_id,
            address_id=data.address_id,
            status=BulkOrderRequestStatus.REQUESTED,
            requested_delivery_date=data.requested_delivery_date,
            customer_notes=data.customer_notes,
        )
        self.db.add(request)
        self.db.flush()

        for item in data.items:
            self.db.add(
                BulkOrderRequestItem(
                    request_id=request.id,
                    product_id=item.product_id,
                    custom_item_name=item.custom_item_name,
                    requested_quantity=item.requested_quantity,
                    unit=item.unit,
                    customer_notes=item.customer_notes,
                )
            )

        self.db.commit()
        self.db.refresh(request)
        logger.info(
            "BULK_ORDER_REQUEST_CREATED: request_id=%s customer_user_id=%s items=%s",
            request.id, user_id, len(data.items),
        )
        return self._to_response(request)

    def list_requests(
        self, user_id: int, page: int, page_size: int
    ) -> BulkOrderRequestListResponse:
        query = self.db.query(BulkOrderRequest).filter(
            BulkOrderRequest.customer_user_id == user_id
        )
        total = query.count()
        items = (
            query.order_by(BulkOrderRequest.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return BulkOrderRequestListResponse(
            items=[self._to_response(r) for r in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_request_detail(self, user_id: int, request_id: int) -> BulkOrderRequestResponse:
        request = self._get_owned_request(user_id, request_id)
        return self._to_response(request)

    def cancel_request(self, user_id: int, request_id: int) -> BulkOrderRequestResponse:
        request = self._lock_request(request_id)
        if request.customer_user_id != user_id:
            raise NotFoundError("Bulk order request not found.")
        self._apply_transition(request, BulkOrderRequestStatus.CANCELLED)
        self.db.commit()
        self.db.refresh(request)
        return self._to_response(request)

    def accept_quote(self, user_id: int, request_id: int) -> BulkOrderRequestResponse:
        """Accepts whatever quote version is currently SENT - the client
        never names a quote_version_id, it is always server-derived from
        the request's own quote.

        Lazy expiry: if the SENT version's `valid_until` (server/database
        date, never client-supplied) has passed, it is transitioned to
        EXPIRED right here instead of ACCEPTED, and the accept is
        rejected - this is what makes quote-acceptance-vs-expiry a race
        with exactly one deterministic outcome rather than a window where
        an expired quote could still be accepted.
        """
        request = self._lock_request(request_id)
        if request.customer_user_id != user_id:
            raise NotFoundError("Bulk order request not found.")
        if BulkOrderRequestStatus(request.status) != BulkOrderRequestStatus.QUOTED:
            raise ConflictError(
                f"Cannot accept a quote for a request in status {request.status}."
            )

        quote = self.db.query(Quote).filter(Quote.request_id == request.id).first()
        if quote is None:
            raise ConflictError("This request has no quote to accept.")

        sent_version = (
            self.db.query(QuoteVersion)
            .filter(
                QuoteVersion.quote_id == quote.id,
                QuoteVersion.status == QuoteVersionStatus.SENT,
            )
            .with_for_update()
            .first()
        )
        if sent_version is None:
            raise ConflictError("This request has no sent quote version to accept.")

        if sent_version.valid_until is not None and sent_version.valid_until < date.today():
            self._transition_quote_version(sent_version, QuoteVersionStatus.EXPIRED)
            self.db.commit()
            logger.warning(
                "BULK_ORDER_QUOTE_EXPIRED_ON_ACCEPT_ATTEMPT: request_id=%s quote_version_id=%s",
                request.id, sent_version.id,
            )
            raise ConflictError("This quote has expired and can no longer be accepted.")

        self._transition_quote_version(sent_version, QuoteVersionStatus.ACCEPTED)
        self._apply_transition(request, BulkOrderRequestStatus.CUSTOMER_ACCEPTED)

        self.db.commit()
        self.db.refresh(request)
        logger.info(
            "BULK_ORDER_QUOTE_ACCEPTED: request_id=%s quote_version_id=%s",
            request.id, sent_version.id,
        )
        return self._to_response(request)

    # ------------------------------------------------------------------
    # Requests - ops-facing
    # ------------------------------------------------------------------

    def admin_get_request_detail(self, request_id: int) -> AdminBulkOrderRequestResponse:
        request = (
            self.db.query(BulkOrderRequest).filter(BulkOrderRequest.id == request_id).first()
        )
        if request is None:
            raise NotFoundError("Bulk order request not found.")
        return self._to_admin_response(request)

    def admin_list_requests(
        self, status: str | None, page: int, page_size: int
    ) -> AdminBulkOrderRequestListResponse:
        query = self.db.query(BulkOrderRequest)
        if status is not None:
            query = query.filter(BulkOrderRequest.status == status)
        total = query.count()
        items = (
            query.order_by(BulkOrderRequest.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return AdminBulkOrderRequestListResponse(
            items=[self._to_admin_response(r) for r in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    def admin_review(self, request_id: int, admin_notes: str | None) -> AdminBulkOrderRequestResponse:
        request = self._lock_request(request_id)
        self._apply_transition(request, BulkOrderRequestStatus.UNDER_REVIEW)
        if admin_notes is not None:
            request.admin_notes = admin_notes
        self.db.commit()
        self.db.refresh(request)
        return self._to_admin_response(request)

    def admin_update_status(
        self, request_id: int, target_status: str, admin_notes: str | None
    ) -> AdminBulkOrderRequestResponse:
        request = self._lock_request(request_id)
        self._apply_transition(request, BulkOrderRequestStatus(target_status))
        if admin_notes is not None:
            request.admin_notes = admin_notes
        self.db.commit()
        self.db.refresh(request)
        return self._to_admin_response(request)

    def create_quote_version(
        self, request_id: int, data: CreateQuoteVersionRequest, created_by_user_id: int
    ) -> QuoteResponse:
        """Creates a DRAFT quote version - private admin work-in-progress,
        not yet visible/actionable by the customer and not yet superseding
        anything. A DRAFT only becomes the customer's operative quote once
        explicitly sent via `send_quote_version`; the request's own status
        does not move to QUOTED until then.

        Drafting is allowed directly from REQUESTED (a straightforward
        request doesn't need a separate "start reviewing" step) as well
        as from UNDER_REVIEW/QUOTED (drafting a revision). A REQUESTED
        request is first silently advanced through UNDER_REVIEW so the
        state machine's strict single-step adjacency is never violated.
        """
        request = self._lock_request(request_id)
        if BulkOrderRequestStatus(request.status) not in _QUOTABLE_STATUSES:
            raise ConflictError(
                f"Cannot quote a request in status {request.status}."
            )
        if BulkOrderRequestStatus(request.status) == BulkOrderRequestStatus.REQUESTED:
            self._apply_transition(request, BulkOrderRequestStatus.UNDER_REVIEW)

        request_items = {
            item.id: item
            for item in self.db.query(BulkOrderRequestItem)
            .filter(BulkOrderRequestItem.request_id == request.id)
            .all()
        }
        variant_ids = {i.variant_id for i in data.items}
        variants = {
            v.id: v
            for v in self.db.query(ProductVariant)
            .filter(ProductVariant.id.in_(variant_ids))
            .all()
        }

        for item in data.items:
            if item.request_item_id not in request_items:
                raise BusinessValidationError(
                    f"request_item_id {item.request_item_id} does not belong to this request."
                )
            if item.variant_id not in variants:
                raise NotFoundError(f"Product variant {item.variant_id} not found.")

        quote = self.db.query(Quote).filter(Quote.request_id == request.id).first()
        if quote is None:
            quote = Quote(request_id=request.id)
            self.db.add(quote)
            self.db.flush()

        next_version_number = (
            self.db.query(QuoteVersion)
            .filter(QuoteVersion.quote_id == quote.id)
            .count()
        ) + 1

        new_version = QuoteVersion(
            quote_id=quote.id,
            version_number=next_version_number,
            status=QuoteVersionStatus.DRAFT,
            currency=data.currency,
            valid_until=data.valid_until,
            admin_notes=data.admin_notes,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(new_version)
        self.db.flush()

        for item in data.items:
            total_price = (item.quantity * item.unit_price).quantize(
                _CENTS, rounding=ROUND_HALF_UP
            )
            self.db.add(
                QuoteItem(
                    quote_version_id=new_version.id,
                    request_item_id=item.request_item_id,
                    variant_id=item.variant_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_price=total_price,
                )
            )

        quote.updated_at = datetime.now(UTC)

        self.db.commit()
        self.db.refresh(quote)
        logger.info(
            "BULK_ORDER_QUOTE_VERSION_DRAFTED: request_id=%s quote_id=%s version_number=%s",
            request.id, quote.id, next_version_number,
        )
        return self._to_quote_response(quote)

    def send_quote_version(
        self, request_id: int, version_id: int, actor_user_id: int
    ) -> QuoteResponse:
        """DRAFT -> SENT: this is the point a quote actually becomes the
        customer's operative offer. Supersedes (never deletes) whatever
        version was previously SENT, and moves the request to QUOTED -
        allowed directly from REQUESTED/UNDER_REVIEW via the same silent
        advance-through-UNDER_REVIEW as `create_quote_version`.
        """
        request = self._lock_request(request_id)
        if BulkOrderRequestStatus(request.status) not in _QUOTABLE_STATUSES:
            raise ConflictError(f"Cannot send a quote for a request in status {request.status}.")

        quote = self.db.query(Quote).filter(Quote.request_id == request.id).first()
        if quote is None:
            raise NotFoundError("No quote exists for this request.")

        draft_version = (
            self.db.query(QuoteVersion)
            .filter(QuoteVersion.id == version_id, QuoteVersion.quote_id == quote.id)
            .with_for_update()
            .first()
        )
        if draft_version is None:
            raise NotFoundError("Quote version not found.")
        if QuoteVersionStatus(draft_version.status) != QuoteVersionStatus.DRAFT:
            # Without this check, re-sending an already-SENT version would
            # match itself as "previous_sent" below and immediately
            # supersede itself (SENT -> SUPERSEDED) instead of being
            # rejected - only a DRAFT can ever be sent.
            raise ConflictError(
                f"Cannot send a quote version in status {draft_version.status}; "
                "only a DRAFT version can be sent."
            )

        previous_sent = (
            self.db.query(QuoteVersion)
            .filter(QuoteVersion.quote_id == quote.id, QuoteVersion.status == QuoteVersionStatus.SENT)
            .with_for_update()
            .first()
        )

        self._transition_quote_version(draft_version, QuoteVersionStatus.SENT)
        if previous_sent is not None:
            self._transition_quote_version(previous_sent, QuoteVersionStatus.SUPERSEDED)

        if BulkOrderRequestStatus(request.status) == BulkOrderRequestStatus.REQUESTED:
            self._apply_transition(request, BulkOrderRequestStatus.UNDER_REVIEW)
        self._apply_transition(request, BulkOrderRequestStatus.QUOTED)
        quote.updated_at = datetime.now(UTC)

        self.db.commit()
        self.db.refresh(quote)
        logger.info(
            "BULK_ORDER_QUOTE_VERSION_SENT: request_id=%s quote_version_id=%s performed_by_user_id=%s",
            request.id, draft_version.id, actor_user_id,
        )
        return self._to_quote_response(quote)

    def reject_quote_version(
        self, request_id: int, version_id: int, actor_user_id: int
    ) -> QuoteResponse:
        """Admin/Operations withdraws a SENT quote version (SENT ->
        REJECTED) - e.g. the terms are no longer viable. Does not by
        itself reject the whole request; admin may still send a new
        version, or separately reject/cancel the request.
        """
        request = self._lock_request(request_id)
        quote = self.db.query(Quote).filter(Quote.request_id == request.id).first()
        if quote is None:
            raise NotFoundError("No quote exists for this request.")

        version = (
            self.db.query(QuoteVersion)
            .filter(QuoteVersion.id == version_id, QuoteVersion.quote_id == quote.id)
            .with_for_update()
            .first()
        )
        if version is None:
            raise NotFoundError("Quote version not found.")

        self._transition_quote_version(version, QuoteVersionStatus.REJECTED)
        quote.updated_at = datetime.now(UTC)

        self.db.commit()
        self.db.refresh(quote)
        logger.info(
            "BULK_ORDER_QUOTE_VERSION_REJECTED: request_id=%s quote_version_id=%s performed_by_user_id=%s",
            request.id, version.id, actor_user_id,
        )
        return self._to_quote_response(quote)

    def get_quote(self, request_id: int) -> QuoteResponse:
        quote = self.db.query(Quote).filter(Quote.request_id == request_id).first()
        if quote is None:
            raise NotFoundError("No quote exists for this request.")
        return self._to_quote_response(quote)

    def get_variant_availability(self, variant_id: int) -> VariantAvailabilityResponse:
        """Read-only: available = quantity - reserved_quantity, summed
        across every ACTIVE lot for this variant (the same pool
        `InventoryReservationService`'s FIFO allocation draws from - see
        its FIFO ALLOCATION SCOPE note). Never mutates inventory and never
        creates a reservation - purely informational so admin can price a
        quote without promising stock that doesn't exist. The real
        reservation only happens at order conversion, which re-checks
        availability under a row lock regardless of what this reports.
        """
        variant = (
            self.db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
        )
        if variant is None:
            raise NotFoundError("Product variant not found.")

        totals = (
            self.db.query(
                func.coalesce(func.sum(InventoryLot.quantity), Decimal("0")),
                func.coalesce(func.sum(InventoryLot.reserved_quantity), Decimal("0")),
            )
            .filter(InventoryLot.variant_id == variant_id, InventoryLot.status == "ACTIVE")
            .first()
        )
        total_quantity, total_reserved = totals
        return VariantAvailabilityResponse(
            variant_id=variant_id,
            total_quantity=total_quantity,
            reserved_quantity=total_reserved,
            available_quantity=total_quantity - total_reserved,
        )

    # ------------------------------------------------------------------
    # Conversion: the ONLY place a bulk request becomes a real Order
    # ------------------------------------------------------------------

    def convert_to_order(self, request_id: int, actor_user_id: int) -> OrderDetailResponse:
        """CUSTOMER_ACCEPTED -> CONVERTED_TO_ORDER. Creates a real Order
        (mirroring OrderService.checkout's own snapshot pattern exactly)
        and its inventory reservation via the unmodified
        InventoryReservationService - see module docstring. Single atomic
        transaction: if reservation fails (insufficient stock), the whole
        conversion rolls back and the request stays CUSTOMER_ACCEPTED for
        a retry, exactly like checkout's own insufficient-stock handling.
        """
        request = self._lock_request(request_id)
        if BulkOrderRequestStatus(request.status) != BulkOrderRequestStatus.CUSTOMER_ACCEPTED:
            raise ConflictError(
                f"Cannot convert a request in status {request.status}."
            )
        if request.address_id is None:
            raise BusinessValidationError(
                "A delivery address is required before this request can be converted to an order."
            )

        address = self.db.query(Address).filter(Address.id == request.address_id).first()
        if not address:
            raise NotFoundError("Address not found.")

        quote = self.db.query(Quote).filter(Quote.request_id == request.id).first()
        if quote is None:
            raise ConflictError("This request has no quote to convert.")
        accepted_version = (
            self.db.query(QuoteVersion)
            .filter(QuoteVersion.quote_id == quote.id, QuoteVersion.status == QuoteVersionStatus.ACCEPTED)
            .first()
        )
        if accepted_version is None:
            raise ConflictError("This request has no accepted quote version.")

        quote_items = (
            self.db.query(QuoteItem)
            .filter(QuoteItem.quote_version_id == accepted_version.id)
            .order_by(QuoteItem.id.asc())
            .all()
        )
        if not quote_items:
            raise ConflictError("The accepted quote has no priced items.")

        variant_ids = {qi.variant_id for qi in quote_items}
        variants = {
            v.id: v
            for v in self.db.query(ProductVariant)
            .filter(ProductVariant.id.in_(variant_ids))
            .all()
        }
        product_ids = {v.product_id for v in variants.values()}
        products = {
            p.id: p for p in self.db.query(Product).filter(Product.id.in_(product_ids)).all()
        }

        total_amount = sum((qi.total_price for qi in quote_items), Decimal("0"))
        order = Order(
            user_id=request.customer_user_id,
            cart_id=None,
            order_number=OrderService._generate_order_number(),
            status="PENDING",
            total_amount=total_amount,
            currency=accepted_version.currency,
            placed_at=datetime.now(UTC),
        )
        self.db.add(order)
        self.db.flush()

        created_items: list[OrderItem] = []
        for qi in quote_items:
            variant = variants[qi.variant_id]
            product = products[variant.product_id]
            order_item = OrderItem(
                order_id=order.id,
                variant_id=variant.id,
                product_name=product.name,
                variant_name=variant.name,
                sku=variant.sku,
                unit=variant.unit,
                quantity=qi.quantity,
                unit_price=qi.unit_price,
                total_price=qi.total_price,
            )
            self.db.add(order_item)
            created_items.append(order_item)
        self.db.flush()

        self.db.add(
            OrderAddress(
                order_id=order.id,
                address_line_1=address.address_line_1,
                address_line_2=address.address_line_2,
                city=address.city,
                state=address.state,
                postal_code=address.postal_code,
                latitude=address.latitude,
                longitude=address.longitude,
            )
        )

        # Reuses the EXISTING, unmodified FIFO reservation service - a
        # converted bulk order is indistinguishable from a retail order
        # from this point forward.
        InventoryReservationService(self.db).create_reservation_for_order(
            order, created_items
        )

        # Database-level idempotency backstop (uq_bulk_order_requests_order_id):
        # even if two conversion attempts somehow both passed the status
        # check above (they cannot, given the row lock, but this is never
        # relied on alone), only one can ever successfully set this
        # column - the second hits a UNIQUE VIOLATION and rolls back.
        request.order_id = order.id
        self._apply_transition(request, BulkOrderRequestStatus.CONVERTED_TO_ORDER)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not convert this request to an order due to a conflicting update."
            ) from exc

        logger.info(
            "BULK_ORDER_CONVERTED: request_id=%s order_id=%s performed_by_user_id=%s",
            request.id, order.id, actor_user_id,
        )
        return self._order_to_detail_response(order)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _lock_request(self, request_id: int) -> BulkOrderRequest:
        """Locks unconditionally on id (no status filter) - same
        retry-safety pattern used throughout this codebase.
        """
        request = (
            self.db.query(BulkOrderRequest)
            .filter(BulkOrderRequest.id == request_id)
            .with_for_update()
            .first()
        )
        if request is None:
            raise NotFoundError("Bulk order request not found.")
        return request

    def _get_owned_request(self, user_id: int, request_id: int) -> BulkOrderRequest:
        request = (
            self.db.query(BulkOrderRequest)
            .filter(
                BulkOrderRequest.id == request_id,
                BulkOrderRequest.customer_user_id == user_id,
            )
            .first()
        )
        if request is None:
            raise NotFoundError("Bulk order request not found.")
        return request

    @staticmethod
    def _apply_transition(
        request: BulkOrderRequest, target: BulkOrderRequestStatus
    ) -> None:
        try:
            result = transition_bulk_order_request_status(
                BulkOrderRequestStatus(request.status), target
            )
        except IllegalBulkOrderRequestTransitionError as exc:
            raise ConflictError(
                f"Cannot move bulk order request from {exc.current.value} to {exc.target.value}."
            ) from exc
        if result.applied:
            request.status = target
            logger.info(
                "BULK_ORDER_REQUEST_STATUS_CHANGED: request_id=%s %s -> %s",
                request.id, result.previous.value, result.current.value,
            )

    @staticmethod
    def _transition_quote_version(
        version: QuoteVersion, target: QuoteVersionStatus
    ) -> None:
        try:
            result = transition_quote_version_status(QuoteVersionStatus(version.status), target)
        except IllegalQuoteVersionTransitionError as exc:
            raise ConflictError(
                f"Cannot move quote version from {exc.current.value} to {exc.target.value}."
            ) from exc
        if result.applied:
            version.status = target

    def _to_response(self, request: BulkOrderRequest) -> BulkOrderRequestResponse:
        items = (
            self.db.query(BulkOrderRequestItem, Product.name)
            .outerjoin(Product, BulkOrderRequestItem.product_id == Product.id)
            .filter(BulkOrderRequestItem.request_id == request.id)
            .order_by(BulkOrderRequestItem.id.asc())
            .all()
        )
        address = (
            self.db.query(Address).filter(Address.id == request.address_id).first()
            if request.address_id
            else None
        )
        return BulkOrderRequestResponse(
            id=request.id,
            status=request.status,
            requested_delivery_date=request.requested_delivery_date,
            customer_notes=request.customer_notes,
            address=BulkOrderRequestAddressResponse.model_validate(address) if address else None,
            items=[
                BulkOrderRequestItemResponse(
                    id=item.id,
                    product_id=item.product_id,
                    product_name=name,
                    custom_item_name=item.custom_item_name,
                    requested_quantity=item.requested_quantity,
                    unit=item.unit,
                    customer_notes=item.customer_notes,
                    created_at=item.created_at,
                )
                for item, name in items
            ],
            created_at=request.created_at,
            updated_at=request.updated_at,
        )

    def _to_admin_response(self, request: BulkOrderRequest) -> AdminBulkOrderRequestResponse:
        base = self._to_response(request)
        return AdminBulkOrderRequestResponse(
            **base.model_dump(),
            customer_user_id=request.customer_user_id,
            admin_notes=request.admin_notes,
        )

    def _to_quote_response(self, quote: Quote) -> QuoteResponse:
        versions = (
            self.db.query(QuoteVersion)
            .filter(QuoteVersion.quote_id == quote.id)
            .order_by(QuoteVersion.version_number.asc())
            .all()
        )
        version_responses = []
        for version in versions:
            rows = (
                self.db.query(QuoteItem, ProductVariant.name, ProductVariant.sku)
                .join(ProductVariant, QuoteItem.variant_id == ProductVariant.id)
                .filter(QuoteItem.quote_version_id == version.id)
                .order_by(QuoteItem.id.asc())
                .all()
            )
            version_responses.append(
                QuoteVersionResponse(
                    id=version.id,
                    version_number=version.version_number,
                    status=version.status,
                    currency=version.currency,
                    valid_until=version.valid_until,
                    admin_notes=version.admin_notes,
                    items=[
                        QuoteItemResponse(
                            id=qi.id,
                            request_item_id=qi.request_item_id,
                            variant_id=qi.variant_id,
                            variant_name=variant_name,
                            sku=sku,
                            quantity=qi.quantity,
                            unit_price=qi.unit_price,
                            total_price=qi.total_price,
                        )
                        for qi, variant_name, sku in rows
                    ],
                    created_at=version.created_at,
                )
            )
        return QuoteResponse(
            id=quote.id,
            request_id=quote.request_id,
            versions=version_responses,
            created_at=quote.created_at,
            updated_at=quote.updated_at,
        )

    def _order_to_detail_response(self, order: Order) -> OrderDetailResponse:
        items = (
            self.db.query(OrderItem)
            .filter(OrderItem.order_id == order.id)
            .order_by(OrderItem.id)
            .all()
        )
        address = (
            self.db.query(OrderAddress).filter(OrderAddress.order_id == order.id).first()
        )
        return OrderDetailResponse(
            **OrderResponse.model_validate(order).model_dump(),
            items=[OrderItemResponse.model_validate(i) for i in items],
            address=OrderAddressResponse.model_validate(address) if address else None,
        )
