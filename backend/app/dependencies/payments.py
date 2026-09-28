"""Payment gateway dependency boundary.

Mirrors the existing `get_db` override pattern (app/dependencies/database.py):
production wiring constructs the real RazorpayGateway from settings; tests
override this dependency with a fake gateway so the full HTTP-level payment
flow is testable without any real gateway connectivity.
"""

from app.core.config import settings
from app.services.payment_gateway import PaymentGateway
from app.services.razorpay_gateway import RazorpayGateway


def get_payment_gateway() -> PaymentGateway:
    return RazorpayGateway(
        key_id=settings.RAZORPAY_KEY_ID,
        key_secret=settings.RAZORPAY_KEY_SECRET,
        webhook_secret=settings.RAZORPAY_WEBHOOK_SECRET,
        base_url=settings.RAZORPAY_BASE_URL,
        timeout_seconds=settings.RAZORPAY_TIMEOUT_SECONDS,
    )
