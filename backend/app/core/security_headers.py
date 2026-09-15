"""Baseline security response headers - none of these were set anywhere in
the backend before this module (confirmed: no header-setting middleware
existed at all). This is a pure-JSON API (no server-rendered HTML pages
except the dev-only /docs, /redoc Swagger UI), so the policy here is
deliberately conservative: headers that are unambiguously correct for a
JSON API and cannot break any legitimate client, rather than a strict CSP
tuned for HTML (which would need per-page tuning this API doesn't have).

Not applied via FastAPI's `docs_url`/`redoc_url` pages specially - those
are already disabled entirely in production (see main.py's
`is_production` check), so a stricter CSP there is unnecessary; the
headers below are safe defaults for both dev and prod.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Every response from this API is JSON (or a redirect/error) -
        # never let a browser sniff a response into executing as HTML/JS.
        response.headers["X-Content-Type-Options"] = "nosniff"

        # This API is never meant to be framed - no legitimate use case,
        # and framing an authenticated JSON API is a clickjacking/data-
        # exfiltration vector for any browser client that does hit it
        # directly (e.g. a webview).
        response.headers["X-Frame-Options"] = "DENY"

        # Minimal CSP appropriate for a JSON API: no scripts/styles are
        # ever served from here, so default-src 'none' with frame-ancestors
        # 'none' (belt-and-braces alongside X-Frame-Options) is correct and
        # cannot break any real client - a JSON response was never going to
        # execute a script or load a frame regardless.
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

        # Never leak the URL (which can carry query-string tokens/PII in a
        # referrer header) to any cross-origin destination.
        response.headers["Referrer-Policy"] = "no-referrer"

        # Disable browser features this API's responses never need -
        # defense in depth if this JSON ever gets rendered somewhere odd
        # (e.g. an iframe despite the headers above).
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        # HSTS only makes sense once the deployment is actually served over
        # HTTPS - forcing it in local HTTP dev would break every dev
        # workflow (docker-compose serves plain HTTP on localhost:8000).
        # See the security report's "Remaining Risks" section: production
        # MUST terminate TLS in front of this service before this header
        # has any real effect, and this flag alone does not provide that.
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

        return response
