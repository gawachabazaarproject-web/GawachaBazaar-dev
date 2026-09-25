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

import httpx

from app.core.config import settings
from app.core.logging import logger

Channel = Literal["EMAIL", "PHONE"]

_RESEND_API_URL = "https://api.resend.com/emails"


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


class NotificationGatewayError(Exception):
    """Raised when a real send genuinely fails (bad API key, provider
    outage, rejected recipient). Never swallowed into a silent success -
    a caller whose entire flow depends on this code arriving (login OTP,
    registration OTP, password reset) needs to know delivery failed
    rather than be told to "check your email" for a code that never sent.
    """


class ResendNotificationGateway:
    """Sends real verification-code emails via Resend's HTTP API
    (https://resend.com/docs/api-reference/emails/send-email). PHONE
    channel is not implemented (no SMS provider exists) - only ever
    reached by ContactChangeService for phone-change verification, itself
    an existing pre-Resend gap, so this logs the same way
    ConsoleNotificationGateway always did for that one case rather than
    pretending Resend can send SMS.
    """

    def __init__(self, *, api_key: str, from_email: str) -> None:
        self._api_key = api_key
        self._from_email = from_email

    def send_verification_code(self, *, channel: Channel, destination: str, code: str) -> None:
        if channel != "EMAIL":
            logger.info(
                "VERIFICATION_CODE_ISSUED: channel=%s destination=%s code=%s "
                "(no SMS gateway configured - this channel still only logs)",
                channel,
                destination,
                code,
            )
            return

        try:
            response = httpx.post(
                _RESEND_API_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "from": self._from_email,
                    "to": [destination],
                    "subject": "Your Gawacha Bazaar verification code",
                    "html": (
                        f"<p>Your Gawacha Bazaar verification code is "
                        f"<strong style='font-size:20px'>{code}</strong>.</p>"
                        f"<p>This code expires in 10 minutes. If you didn't request this, "
                        f"you can safely ignore this email.</p>"
                    ),
                },
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            logger.error(
                "RESEND_SEND_FAILED: destination=%s error=%s", destination, exc
            )
            self._log_code_fallback(destination, code)
            raise NotificationGatewayError(
                "Could not send the verification email."
            ) from exc

        if response.status_code >= 400:
            logger.error(
                "RESEND_SEND_FAILED: destination=%s status=%s body=%s",
                destination,
                response.status_code,
                response.text[:500],
            )
            self._log_code_fallback(destination, code)
            raise NotificationGatewayError("Could not send the verification email.")

        logger.info("RESEND_SEND_SUCCESS: destination=%s", destination)

    @staticmethod
    def _log_code_fallback(destination: str, code: str) -> None:
        """The request still fails loudly (never a silent fake success) -
        this only exists so the code isn't lost entirely while testing
        against Resend's sandbox restriction (unverified domain: only the
        account's own address can receive mail). Once a domain is
        verified this path stops firing for real recipients; it's a
        development safety net, not a production fallback channel."""
        logger.warning(
            "VERIFICATION_CODE_ISSUED_DESPITE_SEND_FAILURE: destination=%s code=%s "
            "(Resend send failed - likely the sandbox one-recipient restriction; "
            "verify a domain at resend.com/domains to lift it)",
            destination,
            code,
        )


def get_default_notification_gateway() -> NotificationGateway:
    """Real Resend delivery when RESEND_API_KEY is configured, otherwise
    the honest console/dev fallback - never a silent no-op either way."""
    if settings.RESEND_API_KEY:
        return ResendNotificationGateway(
            api_key=settings.RESEND_API_KEY, from_email=settings.RESEND_FROM_EMAIL
        )
    return ConsoleNotificationGateway()
