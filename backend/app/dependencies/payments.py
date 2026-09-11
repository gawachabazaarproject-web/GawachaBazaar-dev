"""Payment gateway dependency boundary.

Mirrors the existing `get_db` override pattern (app/dependencies/database.py):
production wiring constructs the real PNBGateway from settings; tests
override this dependency with a FakePNBGateway so the full HTTP-level
payment flow is testable without any real PNB connectivity.
"""

from app.core.config import settings
from app.services.payment_gateway import PaymentGateway, PNBGateway


def get_payment_gateway() -> PaymentGateway:
    return PNBGateway(
        merchant_id=settings.PNB_MERCHANT_ID,
        webhook_secret=settings.PNB_WEBHOOK_SECRET,
        base_url=settings.PNB_BASE_URL,
        timeout_seconds=settings.PNB_TIMEOUT_SECONDS,
    )
