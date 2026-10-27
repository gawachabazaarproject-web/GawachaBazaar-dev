"""Refer & Earn.

Lifecycle:  PENDING --(first eligible delivered order)--> QUALIFIED --> REWARDED
            REWARDED/QUALIFIED --(refund / admin)--> REVERSED
            PENDING --(expiry / admin)--> CANCELLED

Money is only ever written as append-only rows in `referral_reward_ledger`;
there is no balance column. Concurrency safety is layered:
  1. the referral row is locked FOR UPDATE while qualifying / reversing;
  2. the referrer's code row is locked while the reward cap is counted;
  3. UNIQUE(referral_id, beneficiary_user_id, entry_type) in the database is the
     final backstop - a second reward for the same person fails with an
     IntegrityError no matter what the application did.

`qualify_for_order` and `reverse_for_order` run INSIDE the caller's transaction
(delivery confirmation / refund) and never commit. They are wrapped in a
SAVEPOINT by the callers so a referral problem can never block a delivery.
"""

import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.exceptions.base import BusinessValidationError, ConflictError, NotFoundError
from app.models.order import Order
from app.models.referral import Referral, ReferralCode, ReferralRewardLedger
from app.models.user import User
from app.schemas.referral import (
    AdminReferralDetailResponse,
    AdminReferralItem,
    AdminReferralListResponse,
    ApplyReferralResponse,
    ReferralHistoryItem,
    ReferralHistoryResponse,
    ReferralMeResponse,
    ReferralProgramInfo,
    ReferralStats,
    RewardLedgerItem,
    RewardsResponse,
)
from app.services.admin_audit import AdminAuditService

# No 0/O/1/I/L: codes are read aloud and typed from a screenshot.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 8
_ACTIVE_ORDER_STATUSES = ("PENDING", "CONFIRMED", "COMPLETED")
_GENERIC_BLOCK = "This code cannot be used on your account."


def normalize_code(raw: str) -> str:
    return raw.strip().upper()


def _first_name_initial(name: str | None) -> str:
    parts = (name or "").split()
    if not parts:
        return "A customer"
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0]}."


class ReferralService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Program info
    # ------------------------------------------------------------------

    @staticmethod
    def program_info() -> ReferralProgramInfo:
        return ReferralProgramInfo(
            enabled=settings.REFERRAL_ENABLED,
            referrer_reward=settings.REFERRAL_REFERRER_REWARD,
            referred_reward=settings.REFERRAL_REFERRED_REWARD,
            min_order_value=settings.REFERRAL_MIN_ORDER_VALUE,
            qualify_window_days=settings.REFERRAL_QUALIFY_WINDOW_DAYS,
            apply_window_days=settings.REFERRAL_APPLY_WINDOW_DAYS,
        )

    # ------------------------------------------------------------------
    # Customer reads
    # ------------------------------------------------------------------

    def get_or_create_code(self, user_id: int) -> ReferralCode:
        row = self.db.query(ReferralCode).filter(ReferralCode.user_id == user_id).first()
        if row is not None:
            return row
        for _ in range(8):
            candidate = "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LENGTH))
            try:
                with self.db.begin_nested():
                    row = ReferralCode(user_id=user_id, code=candidate)
                    self.db.add(row)
                    self.db.flush()
                self.db.commit()
                return row
            except IntegrityError:
                # Either a code collision (retry) or a concurrent request created
                # this user's code first (return theirs).
                existing = (
                    self.db.query(ReferralCode).filter(ReferralCode.user_id == user_id).first()
                )
                if existing is not None:
                    return existing
        raise ConflictError("Could not create a referral code. Please try again.")

    def me(self, user: User) -> ReferralMeResponse:
        program = self.program_info()
        code_row = self.get_or_create_code(user.id) if program.enabled else None
        counts = dict(
            self.db.query(Referral.status, func.count(Referral.id))
            .filter(Referral.referrer_user_id == user.id)
            .group_by(Referral.status)
            .all()
        )
        earned = self._balance(user.id)
        stats = ReferralStats(
            total_referrals=sum(counts.values()),
            pending=counts.get("PENDING", 0),
            qualified=counts.get("QUALIFIED", 0),
            rewarded=counts.get("REWARDED", 0),
            reversed=counts.get("REVERSED", 0),
            cancelled=counts.get("CANCELLED", 0),
            total_earned=earned,
        )
        already = (
            self.db.query(Referral.id).filter(Referral.referred_user_id == user.id).first()
            is not None
        )
        blocked = self._apply_block_reason(user, already)
        share = None
        if code_row is not None:
            share = (
                f"Join me on Gawacha Bazaar - fresh farm food delivered in Nagpur. "
                f"Use my code {code_row.code} on your first order."
            )
        return ReferralMeResponse(
            code=code_row.code if code_row else None,
            share_message=share,
            program=program,
            stats=stats,
            can_apply_code=blocked is None,
            already_referred=already,
            apply_blocked_reason=blocked,
        )

    def history(self, user_id: int, page: int, page_size: int) -> ReferralHistoryResponse:
        q = self.db.query(Referral).filter(Referral.referrer_user_id == user_id)
        total = q.count()
        rows = (
            q.order_by(Referral.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        )
        names = {
            u.id: u.name
            for u in self.db.query(User).filter(User.id.in_([r.referred_user_id for r in rows]))
        } if rows else {}
        rewards = {}
        if rows:
            for rid, amt in (
                self.db.query(ReferralRewardLedger.referral_id, func.sum(ReferralRewardLedger.amount))
                .filter(
                    ReferralRewardLedger.referral_id.in_([r.id for r in rows]),
                    ReferralRewardLedger.beneficiary_user_id == user_id,
                )
                .group_by(ReferralRewardLedger.referral_id)
                .all()
            ):
                rewards[rid] = amt
        items = [
            ReferralHistoryItem(
                id=r.id,
                referred_display_name=_first_name_initial(names.get(r.referred_user_id)),
                status=r.status,
                applied_at=r.applied_at,
                expires_at=r.expires_at,
                qualified_at=r.qualified_at,
                rewarded_at=r.rewarded_at,
                reward_amount=rewards.get(r.id),
            )
            for r in rows
        ]
        return ReferralHistoryResponse(items=items, total=total, page=page, page_size=page_size)

    def rewards(self, user_id: int, page: int, page_size: int) -> RewardsResponse:
        q = self.db.query(ReferralRewardLedger).filter(
            ReferralRewardLedger.beneficiary_user_id == user_id
        )
        total = q.count()
        rows = (
            q.order_by(ReferralRewardLedger.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return RewardsResponse(
            balance=self._balance(user_id),
            items=[RewardLedgerItem.model_validate(r, from_attributes=True) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def _balance(self, user_id: int) -> Decimal:
        total = (
            self.db.query(func.coalesce(func.sum(ReferralRewardLedger.amount), 0))
            .filter(ReferralRewardLedger.beneficiary_user_id == user_id)
            .scalar()
        )
        return Decimal(total)

    # ------------------------------------------------------------------
    # Apply a code
    # ------------------------------------------------------------------

    def _apply_block_reason(self, user: User, already_referred: bool) -> str | None:
        if not settings.REFERRAL_ENABLED:
            return "Referrals are not available right now."
        if already_referred:
            return "You have already used a referral code."
        if user.created_at is not None and user.created_at < datetime.now(UTC) - timedelta(
            days=settings.REFERRAL_APPLY_WINDOW_DAYS
        ):
            return "Referral codes can only be added shortly after you join."
        has_order = (
            self.db.query(Order.id)
            .filter(Order.user_id == user.id, Order.status.in_(_ACTIVE_ORDER_STATUSES))
            .first()
        )
        if has_order is not None:
            return "Referral codes are for new customers who have not ordered yet."
        return None

    def apply(self, user: User, raw_code: str) -> ApplyReferralResponse:
        if not settings.REFERRAL_ENABLED:
            raise BusinessValidationError("Referrals are not available right now.")
        already = (
            self.db.query(Referral.id).filter(Referral.referred_user_id == user.id).first()
            is not None
        )
        if already:
            raise ConflictError("You have already used a referral code.")
        blocked = self._apply_block_reason(user, already)
        if blocked:
            raise BusinessValidationError(blocked)

        code_row = (
            self.db.query(ReferralCode)
            .filter(ReferralCode.code == normalize_code(raw_code))
            .first()
        )
        if code_row is None:
            raise NotFoundError("Referral code not found.")
        referrer = self.db.query(User).filter(User.id == code_row.user_id).first()
        if referrer is None or referrer.status != "ACTIVE":
            raise NotFoundError("Referral code not found.")

        # Self-referral by id, and by contact (a second account on the same
        # phone / e-mail is the same person).
        if referrer.id == user.id or self._same_contact(referrer, user):
            raise BusinessValidationError(_GENERIC_BLOCK)
        # Circular: the referrer was themselves referred by this user.
        circular = (
            self.db.query(Referral.id)
            .filter(
                Referral.referrer_user_id == user.id,
                Referral.referred_user_id == referrer.id,
            )
            .first()
        )
        if circular is not None:
            raise BusinessValidationError(_GENERIC_BLOCK)

        now = datetime.now(UTC)
        referral = Referral(
            referrer_user_id=referrer.id,
            referred_user_id=user.id,
            referral_code_id=code_row.id,
            status="PENDING",
            applied_at=now,
            expires_at=now + timedelta(days=settings.REFERRAL_QUALIFY_WINDOW_DAYS),
        )
        self.db.add(referral)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            # UNIQUE(referred_user_id): two taps / two devices racing.
            raise ConflictError("You have already used a referral code.") from exc
        self.db.refresh(referral)
        logger.info(
            "REFERRAL_APPLIED: referral_id=%s referrer=%s referred=%s",
            referral.id, referrer.id, user.id,
        )
        return ApplyReferralResponse(
            status=referral.status,
            referrer_display_name=_first_name_initial(referrer.name),
            expires_at=referral.expires_at,
            referred_reward=settings.REFERRAL_REFERRED_REWARD,
            min_order_value=settings.REFERRAL_MIN_ORDER_VALUE,
        )

    @staticmethod
    def _same_contact(a: User, b: User) -> bool:
        if a.email and b.email and a.email.strip().lower() == b.email.strip().lower():
            return True
        # Same number written differently (+91 98.., 98..) is still the same person.
        da = "".join(ch for ch in (a.phone or "") if ch.isdigit())[-10:]
        db = "".join(ch for ch in (b.phone or "") if ch.isdigit())[-10:]
        return bool(da) and da == db

    # ------------------------------------------------------------------
    # Qualification (inside the delivery transaction)
    # ------------------------------------------------------------------

    def qualify_for_order(self, order: Order) -> None:
        """Called with `order` locked and already COMPLETED (delivered). Never
        commits; the caller's transaction owns the outcome."""
        if not settings.REFERRAL_ENABLED or order.status != "COMPLETED":
            return
        referral = (
            self.db.query(Referral)
            .filter(Referral.referred_user_id == order.user_id, Referral.status == "PENDING")
            .populate_existing()
            .with_for_update()
            .first()
        )
        if referral is None:
            return
        now = datetime.now(UTC)
        if referral.expires_at <= now:
            referral.status = "CANCELLED"
            referral.cancelled_at = now
            referral.status_reason = "Expired before a qualifying order."
            return
        items_value = Decimal(order.total_amount) - Decimal(order.delivery_fee)
        if items_value < settings.REFERRAL_MIN_ORDER_VALUE:
            return
        referral.qualifying_order_id = order.id
        referral.status = "QUALIFIED"
        referral.qualified_at = now

        # Serialize the cap check per referrer.
        self.db.query(ReferralCode).filter(
            ReferralCode.id == referral.referral_code_id
        ).with_for_update().first()
        cap = settings.REFERRAL_MAX_REWARDS_PER_REFERRER
        if cap > 0:
            rewarded = (
                self.db.query(func.count(Referral.id))
                .filter(
                    Referral.referrer_user_id == referral.referrer_user_id,
                    Referral.status == "REWARDED",
                )
                .scalar()
            )
            if rewarded >= cap:
                referral.status_reason = "Reward limit reached for this referrer."
                return

        entries = []
        if settings.REFERRAL_REFERRER_REWARD > 0:
            entries.append(("REFERRER", referral.referrer_user_id, settings.REFERRAL_REFERRER_REWARD))
        if settings.REFERRAL_REFERRED_REWARD > 0:
            entries.append(("REFERRED", referral.referred_user_id, settings.REFERRAL_REFERRED_REWARD))
        if not entries:
            return
        for role, beneficiary, amount in entries:
            self.db.add(
                ReferralRewardLedger(
                    referral_id=referral.id,
                    beneficiary_user_id=beneficiary,
                    beneficiary_role=role,
                    entry_type="REWARD",
                    amount=amount,
                    order_id=order.id,
                    reason="Qualifying first order delivered",
                )
            )
        self.db.flush()
        referral.status = "REWARDED"
        referral.rewarded_at = now
        logger.info(
            "REFERRAL_REWARDED: referral_id=%s order_id=%s", referral.id, order.id
        )

    # ------------------------------------------------------------------
    # Reversal / cancellation
    # ------------------------------------------------------------------

    def reverse_for_order(self, order_id: int, reason: str) -> None:
        """Order was refunded: reverse the referral it qualified (no commit)."""
        referral = (
            self.db.query(Referral)
            .filter(Referral.qualifying_order_id == order_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if referral is not None:
            self._reverse_locked(referral, reason, admin_user_id=None)

    def _reverse_locked(self, referral: Referral, reason: str, admin_user_id: int | None) -> None:
        now = datetime.now(UTC)
        if referral.status in ("REVERSED", "CANCELLED"):
            return  # idempotent
        if referral.status == "PENDING":
            referral.status = "CANCELLED"
            referral.cancelled_at = now
            referral.status_reason = reason[:300]
            return
        rewards = (
            self.db.query(ReferralRewardLedger)
            .filter(
                ReferralRewardLedger.referral_id == referral.id,
                ReferralRewardLedger.entry_type == "REWARD",
            )
            .all()
        )
        for r in rewards:
            self.db.add(
                ReferralRewardLedger(
                    referral_id=referral.id,
                    beneficiary_user_id=r.beneficiary_user_id,
                    beneficiary_role=r.beneficiary_role,
                    entry_type="REVERSAL",
                    amount=-r.amount,
                    order_id=r.order_id,
                    reason=reason[:300],
                    created_by_user_id=admin_user_id,
                )
            )
        self.db.flush()
        referral.status = "REVERSED"
        referral.reversed_at = now
        referral.status_reason = reason[:300]
        logger.info("REFERRAL_REVERSED: referral_id=%s", referral.id)

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------

    def admin_list(
        self, status: str | None, user_id: int | None, page: int, page_size: int
    ) -> AdminReferralListResponse:
        q = self.db.query(Referral)
        if status:
            q = q.filter(Referral.status == status)
        if user_id:
            q = q.filter((Referral.referrer_user_id == user_id) | (Referral.referred_user_id == user_id))
        total = q.count()
        rows = q.order_by(Referral.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return AdminReferralListResponse(
            items=[AdminReferralItem.model_validate(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def admin_get(self, referral_id: int) -> AdminReferralDetailResponse:
        r = self.db.query(Referral).filter(Referral.id == referral_id).first()
        if r is None:
            raise NotFoundError("Referral not found.")
        ledger = (
            self.db.query(ReferralRewardLedger)
            .filter(ReferralRewardLedger.referral_id == r.id)
            .order_by(ReferralRewardLedger.id)
            .all()
        )
        base = AdminReferralItem.model_validate(r).model_dump()
        return AdminReferralDetailResponse(
            **base, ledger=[RewardLedgerItem.model_validate(x) for x in ledger]
        )

    def admin_reverse(self, referral_id: int, reason: str, admin_user_id: int) -> AdminReferralDetailResponse:
        referral = (
            self.db.query(Referral)
            .filter(Referral.id == referral_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if referral is None:
            raise NotFoundError("Referral not found.")
        previous = referral.status
        self._reverse_locked(referral, reason, admin_user_id)
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="referral.reverse",
            resource_type="referral",
            resource_id=referral.id,
            previous_state=previous,
            new_state=referral.status,
            reason=reason,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Could not reverse this referral due to a conflicting update.") from exc
        return self.admin_get(referral_id)
