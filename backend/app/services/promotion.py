"""Promotion domain service: admin management + the shared eligibility/
discount engine used identically by the customer-facing preview endpoint
and real checkout - there is exactly one place a discount is ever
computed, so a preview can never disagree with what checkout charges.

CONCURRENCY: `record_redemption` locks the Promotion row
(`.with_for_update()`) and re-validates usage limits UNDER that lock,
inside the same transaction as order creation (see
OrderService.checkout). This is what makes "usage_limit_total=1, two
customers redeem simultaneously" resolve to exactly one success: the
second transaction blocks on the lock, then sees the first transaction's
already-incremented `redemption_count` once it acquires it, and is
rejected - the same pattern already used for InventoryLot/Order/
Reservation locking throughout this codebase, applied to a new resource.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions.base import BusinessValidationError, ConflictError, NotFoundError
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.category import Category
from app.models.order import Order
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.promotion import Promotion
from app.models.promotion_eligible_customer import PromotionEligibleCustomer
from app.models.promotion_redemption import PromotionRedemption
from app.models.promotion_target import PromotionTarget
from app.models.user import User
from app.schemas.promotion import (
    CreatePromotionRequest,
    PromotionDetailResponse,
    PromotionEvaluationResponse,
    PromotionListItemResponse,
    PromotionListResponse,
    PromotionPerformanceResponse,
    PromotionRedemptionListResponse,
    PromotionRedemptionRowResponse,
    PromotionsDashboardResponse,
    PromotionTargetResponse,
    UpdatePromotionRequest,
)
from app.services.pricing import get_current_prices_for_variants
from app.services.admin_audit import AdminAuditService
from app.services.promotion_state import PromotionLike, compute_effective_status, is_currently_redeemable

_CENTS = Decimal("0.01")


@dataclass(frozen=True)
class CartLineForPromo:
    """The minimal shape the engine needs per cart/order line - built by
    the caller (Cart or Checkout) from its own already-loaded rows, never
    re-fetched here."""

    variant_id: int
    product_id: int
    category_id: int
    quantity: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class PromotionEvalResult:
    promotion: Promotion | None
    subtotal: Decimal
    discount_amount: Decimal
    final_total: Decimal
    message: str
    code_was_invalid: bool


class PromotionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Shared engine (preview + checkout)
    # ------------------------------------------------------------------

    def evaluate_for_cart(
        self,
        *,
        user_id: int,
        cart_items: list[CartLineForPromo],
        promo_code: str | None,
        now: datetime,
    ) -> PromotionEvalResult:
        full_subtotal = sum((c.line_total for c in cart_items), Decimal("0"))
        if not cart_items:
            return PromotionEvalResult(None, full_subtotal, Decimal("0"), full_subtotal, "Cart is empty.", False)

        if promo_code:
            code = promo_code.strip().upper()
            promotion = self.db.query(Promotion).filter(Promotion.code == code).first()
            if not promotion:
                return PromotionEvalResult(
                    None, full_subtotal, Decimal("0"), full_subtotal, "This promo code doesn't exist.", True
                )
            if not is_currently_redeemable(self._as_promotion_like(promotion), now):
                return PromotionEvalResult(
                    None, full_subtotal, Decimal("0"), full_subtotal,
                    "This promo code is not currently active.", True,
                )
            if not self._is_customer_eligible(promotion, user_id):
                return PromotionEvalResult(
                    None, full_subtotal, Decimal("0"), full_subtotal,
                    "You are not eligible for this promotion.", True,
                )
            if not self._usage_available(promotion, user_id):
                return PromotionEvalResult(
                    None, full_subtotal, Decimal("0"), full_subtotal,
                    "This promo code has reached its usage limit.", True,
                )
            discount = self._compute_discount(promotion, cart_items, full_subtotal)
            if discount is None:
                reason = (
                    f"Minimum order of {promotion.min_order_value} required."
                    if promotion.min_order_value
                    else "Your cart doesn't qualify for this promotion."
                )
                return PromotionEvalResult(None, full_subtotal, Decimal("0"), full_subtotal, reason, True)
            final_total = full_subtotal - discount
            return PromotionEvalResult(
                promotion, full_subtotal, discount, final_total, f"{promotion.name} applied.", False
            )

        # No code supplied - silently try the single best AUTOMATIC
        # (code IS NULL) promotion. Never an error if none qualifies.
        candidates = (
            self.db.query(Promotion)
            .filter(Promotion.code.is_(None), Promotion.status == "ACTIVE")
            .order_by(Promotion.priority.asc(), Promotion.id.asc())
            .all()
        )
        best_promotion: Promotion | None = None
        best_discount = Decimal("0")
        for promo in candidates:
            if not is_currently_redeemable(self._as_promotion_like(promo), now):
                continue
            if not self._is_customer_eligible(promo, user_id):
                continue
            if not self._usage_available(promo, user_id):
                continue
            discount = self._compute_discount(promo, cart_items, full_subtotal)
            if discount is not None and discount > best_discount:
                best_discount = discount
                best_promotion = promo

        if best_promotion is None:
            return PromotionEvalResult(None, full_subtotal, Decimal("0"), full_subtotal, "No promotion applied.", False)
        final_total = full_subtotal - best_discount
        return PromotionEvalResult(
            best_promotion, full_subtotal, best_discount, final_total,
            f"{best_promotion.name} applied automatically.", False,
        )

    def preview_for_active_cart(self, user_id: int, promo_code: str | None) -> PromotionEvaluationResponse:
        """Customer-facing preview - builds cart lines from the user's own
        ACTIVE cart and runs them through the exact same `evaluate_for_cart`
        engine checkout itself calls, so this can never disagree with what
        checkout actually charges.
        """
        cart = self.db.query(Cart).filter(Cart.user_id == user_id, Cart.status == "ACTIVE").first()
        items = (
            self.db.query(CartItem).filter(CartItem.cart_id == cart.id).all() if cart else []
        )

        cart_lines: list[CartLineForPromo] = []
        if items:
            variant_ids = [i.variant_id for i in items]
            variants = {
                v.id: v for v in self.db.query(ProductVariant).filter(ProductVariant.id.in_(variant_ids)).all()
            }
            product_ids = {v.product_id for v in variants.values()}
            products = {p.id: p for p in self.db.query(Product).filter(Product.id.in_(product_ids)).all()}
            prices = get_current_prices_for_variants(self.db, variant_ids)
            for item in items:
                variant = variants.get(item.variant_id)
                price = prices.get(item.variant_id)
                if not variant or not price:
                    continue
                product = products[variant.product_id]
                line_total = (item.quantity * price.price).quantize(_CENTS, rounding=ROUND_HALF_UP)
                cart_lines.append(
                    CartLineForPromo(
                        variant_id=variant.id,
                        product_id=product.id,
                        category_id=product.category_id,
                        quantity=item.quantity,
                        line_total=line_total,
                    )
                )

        result = self.evaluate_for_cart(
            user_id=user_id, cart_items=cart_lines, promo_code=promo_code, now=datetime.now(UTC)
        )
        return PromotionEvaluationResponse(
            eligible=result.promotion is not None,
            message=result.message,
            promotion_id=result.promotion.id if result.promotion else None,
            promotion_name=result.promotion.name if result.promotion else None,
            applied_code=result.promotion.code if result.promotion else None,
            subtotal=result.subtotal,
            discount_amount=result.discount_amount,
            final_total=result.final_total,
        )

    @staticmethod
    def _as_promotion_like(promotion: Promotion) -> PromotionLike:
        return PromotionLike(status=promotion.status, starts_at=promotion.starts_at, ends_at=promotion.ends_at)

    def _is_customer_eligible(self, promotion: Promotion, user_id: int) -> bool:
        if promotion.customer_scope == "ALL":
            return True
        if promotion.customer_scope == "SPECIFIC":
            return (
                self.db.query(PromotionEligibleCustomer)
                .filter(
                    PromotionEligibleCustomer.promotion_id == promotion.id,
                    PromotionEligibleCustomer.user_id == user_id,
                )
                .first()
                is not None
            )
        has_prior_order = (
            self.db.query(Order.id)
            .filter(Order.user_id == user_id, Order.status.in_(["CONFIRMED", "COMPLETED"]))
            .first()
            is not None
        )
        if promotion.customer_scope == "NEW_CUSTOMERS":
            return not has_prior_order
        if promotion.customer_scope == "EXISTING_CUSTOMERS":
            return has_prior_order
        return False

    def _usage_available(self, promotion: Promotion, user_id: int) -> bool:
        if promotion.usage_limit_total is not None and promotion.redemption_count >= promotion.usage_limit_total:
            return False
        if promotion.usage_limit_per_customer is not None:
            used_by_customer = (
                self.db.query(func.count(PromotionRedemption.id))
                .filter(
                    PromotionRedemption.promotion_id == promotion.id,
                    PromotionRedemption.customer_user_id == user_id,
                    PromotionRedemption.status == "APPLIED",
                )
                .scalar()
            )
            if used_by_customer >= promotion.usage_limit_per_customer:
                return False
        return True

    def _compute_discount(
        self, promotion: Promotion, cart_items: list[CartLineForPromo], full_subtotal: Decimal
    ) -> Decimal | None:
        targets = self.db.query(PromotionTarget).filter(PromotionTarget.promotion_id == promotion.id).all()
        if targets:
            product_ids = {t.target_id for t in targets if t.target_type == "PRODUCT"}
            category_ids = {t.target_id for t in targets if t.target_type == "CATEGORY"}
            applicable = [c for c in cart_items if c.product_id in product_ids or c.category_id in category_ids]
        else:
            applicable = cart_items

        applicable_subtotal = sum((c.line_total for c in applicable), Decimal("0"))
        applicable_quantity = sum((c.quantity for c in applicable), Decimal("0"))

        if applicable_subtotal <= 0:
            return None
        # min_order_value is evaluated against the FULL cart, not just the
        # targeted subset - "spend >=X to unlock Y% off vegetables" is the
        # common real-world semantic (spec section 5's own example:
        # "Minimum Order Discount... ₹100 OFF on orders above ₹999").
        if promotion.min_order_value is not None and full_subtotal < promotion.min_order_value:
            return None
        if promotion.min_quantity is not None and applicable_quantity < promotion.min_quantity:
            return None

        if promotion.discount_type == "PERCENTAGE":
            raw = applicable_subtotal * promotion.discount_value / Decimal("100")
        else:
            raw = promotion.discount_value

        raw = min(raw, applicable_subtotal)
        if promotion.max_discount_amount is not None:
            raw = min(raw, promotion.max_discount_amount)

        return raw.quantize(_CENTS, rounding=ROUND_HALF_UP)

    # ------------------------------------------------------------------
    # Redemption recording / reversal (called from OrderService, same
    # transaction, never commits itself)
    # ------------------------------------------------------------------

    def record_redemption(
        self, *, promotion_id: int, order_id: int, customer_user_id: int, discount_amount: Decimal, now: datetime
    ) -> None:
        promotion = self.db.query(Promotion).filter(Promotion.id == promotion_id).with_for_update().first()
        if promotion is None:
            raise ConflictError("This promotion no longer exists.")
        if promotion.usage_limit_total is not None and promotion.redemption_count >= promotion.usage_limit_total:
            raise ConflictError("This promotion has just reached its usage limit.")
        if promotion.usage_limit_per_customer is not None:
            used = (
                self.db.query(func.count(PromotionRedemption.id))
                .filter(
                    PromotionRedemption.promotion_id == promotion.id,
                    PromotionRedemption.customer_user_id == customer_user_id,
                    PromotionRedemption.status == "APPLIED",
                )
                .scalar()
            )
            if used >= promotion.usage_limit_per_customer:
                raise ConflictError("You have already used this promotion.")

        promotion.redemption_count += 1
        self.db.add(
            PromotionRedemption(
                promotion_id=promotion.id,
                order_id=order_id,
                customer_user_id=customer_user_id,
                discount_amount=discount_amount,
                status="APPLIED",
                redeemed_at=now,
            )
        )

    def reverse_redemption_for_order(self, order_id: int, *, now: datetime) -> None:
        """Cancellation-triggered reversal - frees the promotion's global/
        per-customer usage limit for reuse. The row is marked REVERSED,
        never deleted (historical/audit integrity)."""
        redemption = (
            self.db.query(PromotionRedemption)
            .filter(PromotionRedemption.order_id == order_id, PromotionRedemption.status == "APPLIED")
            .with_for_update()
            .first()
        )
        if redemption is None:
            return
        promotion = (
            self.db.query(Promotion).filter(Promotion.id == redemption.promotion_id).with_for_update().first()
        )
        if promotion is not None and promotion.redemption_count > 0:
            promotion.redemption_count -= 1
        redemption.status = "REVERSED"
        redemption.reversed_at = now

    # ------------------------------------------------------------------
    # Admin: CRUD
    # ------------------------------------------------------------------

    def get_promotion_or_404(self, promotion_id: int) -> Promotion:
        promotion = self.db.query(Promotion).filter(Promotion.id == promotion_id).first()
        if not promotion:
            raise NotFoundError("Promotion not found.")
        return promotion

    def _validate_targets_exist(self, targets: list) -> None:
        product_ids = {t.target_id for t in targets if t.target_type == "PRODUCT"}
        category_ids = {t.target_id for t in targets if t.target_type == "CATEGORY"}
        if product_ids:
            found = {p.id for p in self.db.query(Product.id).filter(Product.id.in_(product_ids)).all()}
            missing = product_ids - found
            if missing:
                raise BusinessValidationError(f"Product id(s) not found: {sorted(missing)}.")
        if category_ids:
            found = {c.id for c in self.db.query(Category.id).filter(Category.id.in_(category_ids)).all()}
            missing = category_ids - found
            if missing:
                raise BusinessValidationError(f"Category id(s) not found: {sorted(missing)}.")

    def create_promotion(self, data: CreatePromotionRequest, admin_user_id: int) -> PromotionDetailResponse:
        if data.ends_at is not None and data.ends_at <= data.starts_at:
            raise BusinessValidationError("End date must be after the start date.")
        self._validate_targets_exist(data.targets)
        if data.customer_scope == "SPECIFIC" and data.eligible_customer_ids:
            found = {
                u.id for u in self.db.query(User.id).filter(User.id.in_(data.eligible_customer_ids)).all()
            }
            missing = set(data.eligible_customer_ids) - found
            if missing:
                raise BusinessValidationError(f"Customer id(s) not found: {sorted(missing)}.")

        promotion = Promotion(
            name=data.name,
            description=data.description,
            customer_title=data.customer_title,
            customer_description=data.customer_description,
            code=data.code,
            discount_type=data.discount_type,
            discount_value=data.discount_value,
            max_discount_amount=data.max_discount_amount,
            min_order_value=data.min_order_value,
            min_quantity=data.min_quantity,
            customer_scope=data.customer_scope,
            status=data.status,
            priority=data.priority,
            usage_limit_total=data.usage_limit_total,
            usage_limit_per_customer=data.usage_limit_per_customer,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            created_by_user_id=admin_user_id,
        )
        self.db.add(promotion)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("A promotion with this code already exists.") from exc

        for t in data.targets:
            self.db.add(PromotionTarget(promotion_id=promotion.id, target_type=t.target_type, target_id=t.target_id))
        for uid in data.eligible_customer_ids:
            self.db.add(PromotionEligibleCustomer(promotion_id=promotion.id, user_id=uid))

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="promotion.create",
            resource_type="promotion",
            resource_id=promotion.id,
            new_state=promotion.status,
            reason=f"code={promotion.code or '(automatic)'}",
        )
        self.db.commit()
        self.db.refresh(promotion)
        return self.admin_get_promotion_detail(promotion.id)

    def update_promotion(
        self, promotion_id: int, data: UpdatePromotionRequest, admin_user_id: int
    ) -> PromotionDetailResponse:
        promotion = self.get_promotion_or_404(promotion_id)
        update_data = data.model_dump(exclude_unset=True, exclude={"targets", "eligible_customer_ids"})
        previous_status = promotion.status

        new_starts = update_data.get("starts_at", promotion.starts_at)
        new_ends = update_data.get("ends_at", promotion.ends_at)
        if new_ends is not None and new_ends <= new_starts:
            raise BusinessValidationError("End date must be after the start date.")

        if data.targets is not None:
            self._validate_targets_exist(data.targets)
        if data.eligible_customer_ids is not None and data.eligible_customer_ids:
            found = {
                u.id for u in self.db.query(User.id).filter(User.id.in_(data.eligible_customer_ids)).all()
            }
            missing = set(data.eligible_customer_ids) - found
            if missing:
                raise BusinessValidationError(f"Customer id(s) not found: {sorted(missing)}.")

        for field, value in update_data.items():
            setattr(promotion, field, value)

        if data.targets is not None:
            self.db.query(PromotionTarget).filter(PromotionTarget.promotion_id == promotion.id).delete()
            for t in data.targets:
                self.db.add(
                    PromotionTarget(promotion_id=promotion.id, target_type=t.target_type, target_id=t.target_id)
                )
        if data.eligible_customer_ids is not None:
            self.db.query(PromotionEligibleCustomer).filter(
                PromotionEligibleCustomer.promotion_id == promotion.id
            ).delete()
            for uid in data.eligible_customer_ids:
                self.db.add(PromotionEligibleCustomer(promotion_id=promotion.id, user_id=uid))

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="promotion.update",
            resource_type="promotion",
            resource_id=promotion.id,
            previous_state=previous_status,
            new_state=promotion.status,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("A promotion with this code already exists.") from exc
        self.db.refresh(promotion)
        return self.admin_get_promotion_detail(promotion.id)

    def duplicate_promotion(self, promotion_id: int, admin_user_id: int) -> PromotionDetailResponse:
        source = self.get_promotion_or_404(promotion_id)
        targets = self.db.query(PromotionTarget).filter(PromotionTarget.promotion_id == source.id).all()
        eligible = (
            self.db.query(PromotionEligibleCustomer)
            .filter(PromotionEligibleCustomer.promotion_id == source.id)
            .all()
        )

        duplicate = Promotion(
            name=f"{source.name} (copy)",
            description=source.description,
            customer_title=source.customer_title,
            customer_description=source.customer_description,
            code=None,  # never reuse the coupon code
            discount_type=source.discount_type,
            discount_value=source.discount_value,
            max_discount_amount=source.max_discount_amount,
            min_order_value=source.min_order_value,
            min_quantity=source.min_quantity,
            customer_scope=source.customer_scope,
            status="DRAFT",
            priority=source.priority,
            usage_limit_total=source.usage_limit_total,
            usage_limit_per_customer=source.usage_limit_per_customer,
            redemption_count=0,
            starts_at=source.starts_at,
            ends_at=source.ends_at,
            created_by_user_id=admin_user_id,
        )
        self.db.add(duplicate)
        self.db.flush()

        for t in targets:
            self.db.add(PromotionTarget(promotion_id=duplicate.id, target_type=t.target_type, target_id=t.target_id))
        for e in eligible:
            self.db.add(PromotionEligibleCustomer(promotion_id=duplicate.id, user_id=e.user_id))

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="promotion.duplicate",
            resource_type="promotion",
            resource_id=duplicate.id,
            new_state="DRAFT",
            reason=f"duplicated_from={source.id}",
        )
        self.db.commit()
        self.db.refresh(duplicate)
        return self.admin_get_promotion_detail(duplicate.id)

    # ------------------------------------------------------------------
    # Admin: reads
    # ------------------------------------------------------------------

    def admin_list_promotions(
        self,
        page: int,
        page_size: int,
        admin_status: str | None = None,
        effective_status: str | None = None,
        q: str | None = None,
    ) -> PromotionListResponse:
        now = datetime.now(UTC)
        query = self.db.query(Promotion).join(User, Promotion.created_by_user_id == User.id)
        if admin_status:
            query = query.filter(Promotion.status == admin_status)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Promotion.name.ilike(like), Promotion.code.ilike(like)))

        if effective_status:
            candidates = query.order_by(Promotion.created_at.desc()).limit(2000).all()
            rows = [self._to_list_item(p, now) for p in candidates]
            matching = [r for r in rows if r.effective_status == effective_status]
            total = len(matching)
            page_items = matching[(page - 1) * page_size : (page - 1) * page_size + page_size]
            return PromotionListResponse(items=page_items, page=page, page_size=page_size, total=total)

        total = query.count()
        promotions = (
            query.order_by(Promotion.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = [self._to_list_item(p, now) for p in promotions]
        return PromotionListResponse(items=items, page=page, page_size=page_size, total=total)

    def _to_list_item(self, promotion: Promotion, now: datetime) -> PromotionListItemResponse:
        return PromotionListItemResponse(
            id=promotion.id,
            name=promotion.name,
            discount_type=promotion.discount_type,
            discount_value=promotion.discount_value,
            code=promotion.code,
            customer_scope=promotion.customer_scope,
            admin_status=promotion.status,
            effective_status=compute_effective_status(self._as_promotion_like(promotion), now).value,
            priority=promotion.priority,
            usage_limit_total=promotion.usage_limit_total,
            redemption_count=promotion.redemption_count,
            starts_at=promotion.starts_at,
            ends_at=promotion.ends_at,
            created_by_name=promotion.created_by.name,
            created_at=promotion.created_at,
            updated_at=promotion.updated_at,
        )

    def admin_get_promotion_detail(self, promotion_id: int) -> PromotionDetailResponse:
        promotion = self.get_promotion_or_404(promotion_id)
        now = datetime.now(UTC)

        targets = self.db.query(PromotionTarget).filter(PromotionTarget.promotion_id == promotion.id).all()
        target_responses = []
        product_ids = {t.target_id for t in targets if t.target_type == "PRODUCT"}
        category_ids = {t.target_id for t in targets if t.target_type == "CATEGORY"}
        product_names = (
            {p.id: p.name for p in self.db.query(Product.id, Product.name).filter(Product.id.in_(product_ids)).all()}
            if product_ids
            else {}
        )
        category_names = (
            {c.id: c.name for c in self.db.query(Category.id, Category.name).filter(Category.id.in_(category_ids)).all()}
            if category_ids
            else {}
        )
        for t in targets:
            name = product_names.get(t.target_id) if t.target_type == "PRODUCT" else category_names.get(t.target_id)
            target_responses.append(PromotionTargetResponse(target_type=t.target_type, target_id=t.target_id, target_name=name))

        eligible_customer_ids = [
            e.user_id
            for e in self.db.query(PromotionEligibleCustomer)
            .filter(PromotionEligibleCustomer.promotion_id == promotion.id)
            .all()
        ]

        performance = self._compute_performance(promotion.id)

        return PromotionDetailResponse(
            id=promotion.id,
            name=promotion.name,
            description=promotion.description,
            customer_title=promotion.customer_title,
            customer_description=promotion.customer_description,
            code=promotion.code,
            discount_type=promotion.discount_type,
            discount_value=promotion.discount_value,
            max_discount_amount=promotion.max_discount_amount,
            min_order_value=promotion.min_order_value,
            min_quantity=promotion.min_quantity,
            customer_scope=promotion.customer_scope,
            eligible_customer_ids=eligible_customer_ids,
            admin_status=promotion.status,
            effective_status=compute_effective_status(self._as_promotion_like(promotion), now).value,
            stacking_policy=promotion.stacking_policy,
            priority=promotion.priority,
            usage_limit_total=promotion.usage_limit_total,
            usage_limit_per_customer=promotion.usage_limit_per_customer,
            redemption_count=promotion.redemption_count,
            starts_at=promotion.starts_at,
            ends_at=promotion.ends_at,
            targets=target_responses,
            created_by_name=promotion.created_by.name,
            created_at=promotion.created_at,
            updated_at=promotion.updated_at,
            performance=performance,
        )

    def _compute_performance(self, promotion_id: int) -> PromotionPerformanceResponse:
        applied = (
            self.db.query(PromotionRedemption)
            .filter(PromotionRedemption.promotion_id == promotion_id, PromotionRedemption.status == "APPLIED")
            .all()
        )
        reversed_count = (
            self.db.query(func.count(PromotionRedemption.id))
            .filter(PromotionRedemption.promotion_id == promotion_id, PromotionRedemption.status == "REVERSED")
            .scalar()
            or 0
        )
        total_discount = sum((r.discount_amount for r in applied), Decimal("0"))
        order_ids = [r.order_id for r in applied]
        revenue_influenced = Decimal("0")
        if order_ids:
            revenue_influenced = (
                self.db.query(func.coalesce(func.sum(Order.total_amount), 0))
                .filter(Order.id.in_(order_ids))
                .scalar()
                or Decimal("0")
            )
        avg_order_value = (revenue_influenced / len(applied)) if applied else None
        return PromotionPerformanceResponse(
            redemption_count=len(applied),
            reversed_count=reversed_count,
            total_discount_granted=total_discount,
            revenue_influenced=Decimal(revenue_influenced),
            average_order_value=avg_order_value.quantize(_CENTS) if avg_order_value is not None else None,
        )

    def list_redemptions(self, promotion_id: int, page: int, page_size: int) -> PromotionRedemptionListResponse:
        self.get_promotion_or_404(promotion_id)
        query = (
            self.db.query(PromotionRedemption, Order.order_number, Order.status, Order.total_amount, User.name)
            .join(Order, PromotionRedemption.order_id == Order.id)
            .join(User, PromotionRedemption.customer_user_id == User.id)
            .filter(PromotionRedemption.promotion_id == promotion_id)
        )
        total = query.count()
        rows = (
            query.order_by(PromotionRedemption.redeemed_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = [
            PromotionRedemptionRowResponse(
                id=r.id,
                order_id=r.order_id,
                order_number=order_number,
                order_status=order_status,
                customer_id=r.customer_user_id,
                customer_name=customer_name,
                discount_amount=r.discount_amount,
                order_total=order_total,
                status=r.status,
                redeemed_at=r.redeemed_at,
            )
            for r, order_number, order_status, order_total, customer_name in rows
        ]
        return PromotionRedemptionListResponse(items=items, page=page, page_size=page_size, total=total)

    def admin_dashboard(self) -> PromotionsDashboardResponse:
        now = datetime.now(UTC)
        promotions = self.db.query(Promotion).all()
        counts = {"ACTIVE": 0, "SCHEDULED": 0, "EXPIRED": 0, "DRAFT": 0, "DISABLED": 0, "PAUSED": 0}
        for p in promotions:
            eff = compute_effective_status(self._as_promotion_like(p), now).value
            counts[eff] = counts.get(eff, 0) + 1

        total_redemptions = (
            self.db.query(func.count(PromotionRedemption.id))
            .filter(PromotionRedemption.status == "APPLIED")
            .scalar()
            or 0
        )
        total_discount = (
            self.db.query(func.coalesce(func.sum(PromotionRedemption.discount_amount), 0))
            .filter(PromotionRedemption.status == "APPLIED")
            .scalar()
            or Decimal("0")
        )

        ending_soon = (
            self.db.query(Promotion)
            .join(User, Promotion.created_by_user_id == User.id)
            .filter(Promotion.status == "ACTIVE", Promotion.ends_at.isnot(None), Promotion.ends_at >= now)
            .order_by(Promotion.ends_at.asc())
            .limit(5)
            .all()
        )
        most_used = (
            self.db.query(Promotion)
            .join(User, Promotion.created_by_user_id == User.id)
            .filter(Promotion.redemption_count > 0)
            .order_by(Promotion.redemption_count.desc())
            .limit(5)
            .all()
        )

        return PromotionsDashboardResponse(
            active_count=counts["ACTIVE"],
            scheduled_count=counts["SCHEDULED"],
            expired_count=counts["EXPIRED"],
            draft_count=counts["DRAFT"],
            disabled_count=counts["DISABLED"],
            paused_count=counts["PAUSED"],
            total_redemptions=total_redemptions,
            total_discount_granted=Decimal(total_discount),
            ending_soon=[self._to_list_item(p, now) for p in ending_soon],
            most_used=[self._to_list_item(p, now) for p in most_used],
        )
