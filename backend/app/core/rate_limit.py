"""Rate limiting for the handful of endpoints this app's own threat model
identifies as abuse-prone: login, registration, and refresh-token rotation
(OWASP API Security Top 10 - API4 Unrestricted Resource Consumption, API6
Sensitive Business Flow Abuse). Before this module, nothing in the backend
throttled repeated requests at all - confirmed by a full search of
requirements.txt and every dependency/middleware for a rate-limiting
library.

In-memory, per-process limiter (slowapi wraps the `limits` package). This
is correct for the application's current single-instance deployment (see
docker-compose.yml - one backend container, no load balancer). If the
backend is ever horizontally scaled, this must move to a shared backend
(e.g. Redis via `limits`' RedisStorage) or these limits silently become
per-instance instead of global - flagging that now so the migration isn't
missed later.

Deliberately NOT applied globally: blanket rate limiting on read-heavy
catalog/admin browsing would risk breaking legitimate usage (an admin
paging through orders, a customer browsing the catalog) for no real
security benefit against this app's actual risk profile. Scoped only to
the specific flows that are genuinely abuse-prone.
"""

import hashlib

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

limiter = Limiter(key_func=get_remote_address)


def user_or_ip_key(request: Request) -> str:
    """Per-signed-in-user key (hash of the bearer token), else the client IP.
    Used for customer endpoints: mobile carriers in India put many users behind
    one NAT address, so a pure per-IP limit would throttle innocent neighbours.
    The token is hashed, never stored or logged."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer ") and len(auth) > 20:
        return "u:" + hashlib.sha256(auth[7:].encode()).hexdigest()[:20]
    return get_remote_address(request)
