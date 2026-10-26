"""POST /delivery/quote: address id -> coordinates -> road distance -> fee.

Everything is looked up server-side: the address (must belong to the caller,
else 404), the warehouse, the route and the pricing rules. The fee uses the
caller's current cart (Bazaar = free) through the same
`calculate_delivery_fee` that checkout uses.
"""

import logging

from sqlalchemy.orm import Session

from app.exceptions.base import BusinessValidationError, NotFoundError
from app.models.address import Address
from app.schemas.delivery import DeliveryQuoteResponse
from app.services.bazaar import BazaarService
from app.services.delivery import (
    DeliveryUnavailableError,
    calculate_delivery_fee,
    get_packing_origin,
)

logger = logging.getLogger(__name__)


class DeliveryQuoteService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def quote(self, user_id: int, address_id: int) -> DeliveryQuoteResponse:
        address = (
            self.db.query(Address)
            .filter(Address.id == address_id, Address.user_id == user_id)
            .first()
        )
        if address is None:
            raise NotFoundError("Address not found.")
        if address.latitude is None or address.longitude is None:
            raise BusinessValidationError(
                "This address has no map location yet. Confirm its location first."
            )

        logger.info("delivery_quote_requested address_id=%s user_id=%s", address.id, user_id)
        o_lat, o_lon, warehouse_id = get_packing_origin(self.db)
        if o_lat is None or o_lon is None:
            # Misconfiguration, not a customer problem: never guess a distance.
            raise BusinessValidationError("Delivery origin is not configured.")

        item_count = BazaarService(self.db)._cart_product_count(user_id)
        try:
            q = calculate_delivery_fee(
                item_count,
                address.latitude,
                address.longitude,
                origin=(o_lat, o_lon),
                warehouse_id=warehouse_id,
            )
        except DeliveryUnavailableError as exc:
            return DeliveryQuoteResponse(
                available=False,
                distance_km=exc.distance_km,
                delivery_fee=None,
                reason=exc.message,
            )
        return DeliveryQuoteResponse(
            available=True,
            distance_km=q.distance_km,
            distance_meters=q.distance_meters,
            estimated_duration_minutes=(
                None if q.duration_seconds is None else round(q.duration_seconds / 60)
            ),
            delivery_fee=q.fee,
            free_delivery=q.free_delivery,
        )
