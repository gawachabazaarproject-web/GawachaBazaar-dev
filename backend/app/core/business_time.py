"""The business's calendar day.

Expiry dates are dates the shop reads off a calendar, so "today", "tomorrow"
and "expired" must follow the shop's timezone (BAZAAR_TIMEZONE, Asia/Kolkata by
default) - not the server's clock and not UTC, which in India is still
"yesterday" until 05:30 in the morning.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def business_today() -> date:
    return datetime.now(ZoneInfo(settings.BAZAAR_TIMEZONE)).date()
