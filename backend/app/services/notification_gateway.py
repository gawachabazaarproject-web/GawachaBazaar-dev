"""Notification gateway interface and the console adapter boundary.

Same honest-boundary pattern as app/services/payment_gateway.py's PNBGateway:
this backend has no email/SMS provider configured anywhere (no SMTP/
SendGrid/SES/Twilio settings exist in app/core/config.py - confirmed before
writing this module), so `ConsoleNotificationGateway` does not pretend to
send a real email or SMS. It logs the verification code server-side via the
existing app logger, which is the standard "console"/"sandbox" mail-transport
pattern many frameworks ship for local development (Django's console email
backend, Rails' letter_opener) - an honestly-labeled dev channel, not a
simulated real delivery the way faking a payment-gateway success would be.

`ContactChangeService` depends only on the `NotificationGateway` protocol
below, so swapping in a real provider later (SES, Twilio, etc.) is a new
adapter class, not a change to the verification business logic.
"""

from typing import Literal, Protocol

from app.core.logging import logger

Channel = Literal["EMAIL", "PHONE"]


class NotificationGateway(Protocol):
    def send_verification_code(self, *, channel: Channel, destination: str, code: str) -> None: ...


class ConsoleNotificationGateway:
    """Dev/placeholder adapter: logs the code instead of sending a real
    email/SMS. Whoever can read the backend's own logs (i.e. an operator,
    not the customer) can retrieve it - acceptable for a dev environment
    with no real provider, never for production use.
    """

    def send_verification_code(self, *, channel: Channel, destination: str, code: str) -> None:
        logger.info(
            "VERIFICATION_CODE_ISSUED: channel=%s destination=%s code=%s "
            "(no real email/SMS gateway configured - this is a dev/placeholder channel)",
            channel,
            destination,
            code,
        )
