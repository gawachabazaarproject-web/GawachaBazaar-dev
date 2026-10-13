"""Offers carousel: the live promotions an admin chose to advertise.

An offer is simply a Promotion with `show_in_carousel` switched on, so the
carousel can never advertise something checkout would refuse: the same
"currently redeemable" rule (status ACTIVE + inside its dates) and the same
usage-limit check gate both. Promotions limited to specific customers are
never advertised.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.promotion import Promotion
from app.schemas.offer import OfferResponse
from app.services.promotion_state import PromotionLike, is_currently_redeemable

MAX_OFFERS = 10

_AUDIENCE = {"NEW_CUSTOMERS": "New customers", "EXISTING_CUSTOMERS": "Returning customers"}


def _money(value: Decimal) -> str:
    return f"Rs {value.quantize(Decimal('1')):,}" if value == value.to_integral_value() else f"Rs {value:,.2f}"


def _percent(value: Decimal) -> str:
    return f"{value.normalize():f}%"


def discount_label(promotion: Promotion) -> str:
    if promotion.discount_type == "PERCENTAGE":
        return f"{_percent(promotion.discount_value)} OFF"
    return f"{_money(promotion.discount_value)} OFF"


def fine_print(promotion: Promotion) -> str | None:
    parts = []
    if promotion.min_order_value is not None:
        parts.append(f"On orders above {_money(promotion.min_order_value)}")
    if promotion.max_discount_amount is not None and promotion.discount_type == "PERCENTAGE":
        parts.append(f"up to {_money(promotion.max_discount_amount)} off")
    return " - ".join(parts) if parts else None


class OfferService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_live_offers(self, now: datetime | None = None) -> list[OfferResponse]:
        now = now or datetime.now(UTC)
        candidates = (
            self.db.query(Promotion)
            .filter(
                Promotion.show_in_carousel.is_(True),
                Promotion.status == "ACTIVE",
                Promotion.customer_scope != "SPECIFIC",
            )
            .order_by(Promotion.priority.asc(), Promotion.id.asc())
            .all()
        )
        offers: list[OfferResponse] = []
        for promotion in candidates:
            if not is_currently_redeemable(
                PromotionLike(status=promotion.status, starts_at=promotion.starts_at, ends_at=promotion.ends_at), now
            ):
                continue
            if (
                promotion.usage_limit_total is not None
                and promotion.redemption_count >= promotion.usage_limit_total
            ):
                continue
            offers.append(
                OfferResponse(
                    id=promotion.id,
                    title=promotion.customer_title or promotion.name,
                    description=promotion.customer_description or promotion.description or "",
                    image_url=promotion.image_url,
                    code=promotion.code,
                    discount_label=discount_label(promotion),
                    fine_print=fine_print(promotion),
                    audience=_AUDIENCE.get(promotion.customer_scope),
                    ends_at=promotion.ends_at,
                )
            )
            if len(offers) >= MAX_OFFERS:
                break
        return offers
