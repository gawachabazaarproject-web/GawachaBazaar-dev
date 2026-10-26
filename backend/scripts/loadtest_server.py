"""DEV/STAGING LOAD-TEST SERVER - NEVER RUN IN PRODUCTION.

Runs the real FastAPI app, but replaces Firebase with a stub that accepts the
deterministic tokens `lt-<n>` (user n). Used only by scripts/loadtest_api.py so
authenticated endpoints can be load tested without real Firebase accounts.
Refuses to start unless APP_ENV is development/testing/staging AND
LOADTEST_ALLOW_FAKE_AUTH=1.

    LOADTEST_ALLOW_FAKE_AUTH=1 DATABASE_URL=<disposable db> \\
    python scripts/loadtest_server.py --port 18000
"""

import argparse
import os
import sys

import uvicorn

from app.core.config import settings
from app.core.firebase import (
    FirebaseGateway,
    FirebaseIdentity,
    FirebaseTokenError,
    set_firebase,
)


class LoadTestFirebase(FirebaseGateway):
    def verify_id_token(self, token: str) -> FirebaseIdentity:
        if not token.startswith("lt-"):
            raise FirebaseTokenError("invalid")
        # Token format: lt-<n>-<padding>. Padding makes it as long as a real
        # Firebase token so per-user rate-limit keys behave like production.
        uid = "-".join(token.split("-")[:2])
        return FirebaseIdentity(
            uid=uid, email=f"{uid}@loadtest.example", email_verified=True,
            phone=None, name=uid, sign_in_provider="password",
        )

    def create_user(self, **_k):  # pragma: no cover - not used by the load test
        raise NotImplementedError

    def update_password(self, *_a):  # pragma: no cover
        raise NotImplementedError

    def set_disabled(self, *_a):  # pragma: no cover
        raise NotImplementedError

    def revoke_sessions(self, *_a):  # pragma: no cover
        raise NotImplementedError

    def delete_user(self, *_a):  # pragma: no cover
        raise NotImplementedError


if __name__ == "__main__":
    if settings.APP_ENV == "production" or os.environ.get("LOADTEST_ALLOW_FAKE_AUTH") != "1":
        sys.exit("refusing to start: fake auth is for disposable load-test environments only")
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18000)
    args = ap.parse_args()
    set_firebase(LoadTestFirebase())
    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=args.port, workers=1, log_level="warning", access_log=False)
