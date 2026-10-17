"""One simulated backend replica, started exactly like start.sh does
(uvicorn --proxy-headers --forwarded-allow-ips "*", 1 worker) but against a
validated local disposable DB and with a portable Firebase fake, so two of
these processes behave like two pods behind a load balancer.

Run only by tests/multiproc/run_scenarios.py. Not collected by pytest.
"""

import os

from tests._db_safety import resolve_test_database_url

_url = resolve_test_database_url(os.environ)  # fail closed before importing app
os.environ["DATABASE_URL"] = _url
os.environ["APP_ENV"] = "testing"
for _n in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET", "CLOUDINARY_CLOUD_NAME",
           "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET", "GOOGLE_MAPS_API_KEY", "FIREBASE_SERVICE_ACCOUNT_JSON"):
    os.environ[_n] = ""

import app.main as main_module  # noqa: E402
from app.core.firebase import FirebaseIdentity, FirebaseTokenError, set_firebase  # noqa: E402
from tests.firebase_fake import FakeFirebase  # noqa: E402

# Short sweep interval so redundancy between replicas is observable in seconds.
main_module.RESERVATION_EXPIRY_SWEEP_INTERVAL_SECONDS = float(os.environ.get("MP_SWEEP_SECONDS", "2"))


class PortableFirebase(FakeFirebase):
    """Accepts tokens `mp.<uid>` on every replica, like real Firebase tokens
    verify on any pod (the stock fake keeps tokens in per-process memory)."""

    def verify_id_token(self, token: str) -> FirebaseIdentity:
        if not token.startswith("mp."):
            raise FirebaseTokenError("invalid")
        uid = token[3:]
        return FirebaseIdentity(uid=uid, email=f"{uid}@mp.test", email_verified=True,
                                phone=None, name=None, sign_in_provider="google.com")


set_firebase(PortableFirebase())
app = main_module.app
