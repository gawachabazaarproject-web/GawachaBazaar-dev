import json
from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # `FOO=` (blank, as in .env.example) means "use the default"; without
        # this a blank numeric setting such as PACKING_POINT_LATITUDE= crashes startup.
        env_ignore_empty=True,
        case_sensitive=True,
    )

    APP_NAME: str = "GawachaBazaar"
    APP_ENV: Literal["development", "testing", "staging", "production"] = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Firebase Authentication. Firebase owns every credential (passwords,
    # Google OAuth, phone OTP); this backend only verifies Firebase ID
    # tokens with the Admin SDK and maps the verified UID to a `users` row.
    # FIREBASE_SERVICE_ACCOUNT_JSON is the service-account key JSON as a
    # single secret env value (host secret) - never commit it. When it is
    # empty, Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS)
    # are used instead. ID-token verification itself only needs the
    # project id; the key is needed for admin operations (creating staff
    # accounts, password resets, migrating legacy accounts).
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_SERVICE_ACCOUNT_JSON: str = ""

    # Database
    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/gawachabazaar"
    )

    # Razorpay (online payments - UPI, cards, netbanking, wallets via
    # Standard Checkout; see app/services/razorpay_gateway.py). Empty key
    # id means "not configured": online payment is refused with a clear
    # 503 and Cash on Delivery keeps working. KEY_SECRET and WEBHOOK_SECRET
    # never leave the server; KEY_ID is public (sent to Checkout).
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    RAZORPAY_BASE_URL: str = "https://api.razorpay.com/v1"
    RAZORPAY_TIMEOUT_SECONDS: float = 10.0

    # Delivery pricing + the "Bazaar" offer. A basket with at least
    # FREE_DELIVERY_MIN_ITEMS DIFFERENT PRODUCTS ships free (a product bought
    # in several sizes/quantities still counts once); smaller baskets pay
    # DELIVERY_BASE_FEE + DELIVERY_PER_KM per km of road distance
    # from the packing point to the delivery address (distance counted up
    # to DELIVERY_MAX_CHARGED_KM, so one bad coordinate can never produce a
    # absurd fee). PACKING_POINT_LATITUDE/LONGITUDE must be set for the
    # per-km part to apply; without them (or without GPS on the address)
    # only the base fee is charged. A customer with BAZAAR_PLUS_ORDERS_REQUIRED
    # Bazaar orders (each with >= FREE_DELIVERY_MIN_ITEMS different products)
    # in the current calendar month (BAZAAR_TIMEZONE) is eligible for
    # Gawacha Bazaar+.
    FREE_DELIVERY_MIN_ITEMS: int = 10
    DELIVERY_BASE_FEE: Decimal = Decimal("20")
    DELIVERY_PER_KM: Decimal = Decimal("10")
    DELIVERY_MAX_CHARGED_KM: float = 30.0
    # Fallback origin; the admin-chosen packing point (Settings page) wins.
    PACKING_POINT_LATITUDE: float | None = None
    PACKING_POINT_LONGITUDE: float | None = None
    # PostgreSQL pool (per worker; production runs ONE worker, so this is also the
    # per-instance total). Keep pool_size + max_overflow well below the RDS
    # max_connections (db.t4g.micro ~ 110) after adding any second worker/replica.
    # The timeouts are applied server-side on every connection; 0 disables one.
    DB_POOL_SIZE: int = 12
    DB_MAX_OVERFLOW: int = 12
    # In-flight HTTP request cap; MUST be <= DB_POOL_SIZE + DB_MAX_OVERFLOW (each
    # request holds a connection) - see app/core/concurrency.py. 0 disables.
    MAX_INFLIGHT_REQUESTS: int = 24
    INFLIGHT_QUEUE_TIMEOUT_SECONDS: float = 15.0
    DB_POOL_TIMEOUT_SECONDS: int = 10
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_STATEMENT_TIMEOUT_MS: int = 20000
    DB_IDLE_IN_TRANSACTION_TIMEOUT_MS: int = 60000

    # Road-distance routing (OpenStreetMap-based, no paid API). ROUTING_PROVIDER
    # selects the RoutingProvider; "osrm" is the only one today. The public OSRM
    # demo server is for development/testing only - self-host OSRM in production
    # (docs/05-domains/DELIVERY.md). If routing fails the quote FAILS (503): a
    # straight-line guess is never presented as a road distance.
    ROUTING_PROVIDER: Literal["osrm"] = "osrm"
    OSRM_BASE_URL: str = "https://router.project-osrm.org"
    ROUTING_TIMEOUT_SECONDS: float = 3.0
    # Customers farther than this by road cannot be delivered to. 0 = no limit
    # (the previous behaviour; the fee is still capped by DELIVERY_MAX_CHARGED_KM).
    DELIVERY_MAX_DISTANCE_KM: float = 0.0
    # Orders below this subtotal (after discount) are refused at checkout. 0 = off.
    DELIVERY_MIN_ORDER_VALUE: Decimal = Decimal("0")
    # Redis caches road distances only (never fees). Empty = in-process cache.
    # Redis being down never breaks delivery - routing is simply called directly.
    REDIS_URL: str = ""
    ROUTE_CACHE_TTL_SECONDS: int = 7 * 24 * 3600
    # Geocoding (address search -> coordinates). Public Nominatim allows ~1
    # request/second and forbids autocomplete; it needs an identifying User-Agent.
    GEOCODING_PROVIDER: Literal["nominatim"] = "nominatim"
    NOMINATIM_BASE_URL: str = "https://nominatim.openstreetmap.org"
    NOMINATIM_USER_AGENT: str = "GawachaBazaar/1.0 (gawachabazaar.project@gmail.com)"
    GEOCODING_TIMEOUT_SECONDS: float = 5.0
    BAZAAR_PLUS_ORDERS_REQUIRED: int = 6
    BAZAAR_TIMEZONE: str = "Asia/Kolkata"

    # ------------------------------------------------------------------
    # Refer & Earn. REQUIRED BUSINESS DECISION: every value below is a
    # PLACEHOLDER chosen only so the code is safe, not a company policy. The
    # feature ships DISABLED (REFERRAL_ENABLED=false): nothing can be applied,
    # qualified or rewarded until the owner decides the rewards and turns it
    # on. See docs/05-domains/REFERRAL_SYSTEM.md.
    # ------------------------------------------------------------------
    REFERRAL_ENABLED: bool = False
    REFERRAL_REFERRER_REWARD: Decimal = Decimal("50")  # Rs credited to the inviter
    REFERRAL_REFERRED_REWARD: Decimal = Decimal("50")  # Rs credited to the new customer
    REFERRAL_MIN_ORDER_VALUE: Decimal = Decimal("199")  # items value after discount, excl. delivery
    REFERRAL_APPLY_WINDOW_DAYS: int = 14  # a code can be applied this long after sign-up
    REFERRAL_QUALIFY_WINDOW_DAYS: int = 30  # applied -> first qualifying order deadline
    REFERRAL_MAX_REWARDS_PER_REFERRER: int = 20  # 0 = unlimited

    # ------------------------------------------------------------------
    # Delivery partners. REQUIRED BUSINESS DECISION: the partner's earning
    # is NOT the customer's delivery fee. These rupee values are placeholders;
    # the result is snapshotted on every earnings ledger row.
    # ------------------------------------------------------------------
    PARTNER_EARNING_RULE_VERSION: str = "partner-v1"
    PARTNER_EARNING_BASE: Decimal = Decimal("20")
    PARTNER_EARNING_PER_KM: Decimal = Decimal("5")
    PARTNER_EARNING_COD_BONUS: Decimal = Decimal("0")

    # COD delivery OTP: the customer reads a 6-digit code to the partner; the
    # backend alone generates, stores (HMAC hash) and verifies it. DELIVERY_OTP_SECRET
    # is the HMAC/encryption key (>= 32 chars, required in production when enforced).
    # DELIVERY_OTP_ENFORCED=false is a rollout switch: COD orders can then be
    # completed without a code (the code is still issued if the partner asks).
    DELIVERY_OTP_ENFORCED: bool = True
    DELIVERY_OTP_SECRET: str = ""
    DELIVERY_OTP_EXPIRY_MINUTES: int = 240
    DELIVERY_OTP_MAX_ATTEMPTS: int = 5
    DELIVERY_OTP_RESEND_LIMIT: int = 3
    DELIVERY_OTP_RESEND_WINDOW_MINUTES: int = 15
    # Live location: minimum seconds between accepted updates per assignment,
    # the largest plausible speed between two updates, and how old a position
    # may be before a customer stops seeing it.
    PARTNER_LOCATION_MIN_INTERVAL_SECONDS: int = 3
    PARTNER_LOCATION_MAX_SPEED_KMH: float = 150.0
    PARTNER_LOCATION_STALE_SECONDS: int = 300

    # Cloudinary (image uploads). Empty string means "not configured" -
    # ImageUploadService raises a clear, honest error rather than silently
    # failing if an upload route is ever called before these are set,
    # same "don't fabricate a working integration" precedent as
    # PaymentGateway.
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_database_url(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("postgres://"):
                return "postgresql+psycopg://" + v[len("postgres://"):]
            if v.startswith("postgresql://") and not v.startswith("postgresql+"):
                return "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed]
                except Exception:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        if isinstance(v, (list, tuple)):
            return [str(item).strip() for item in v]
        return []

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_testing(self) -> bool:
        return self.APP_ENV == "testing"

    @model_validator(mode="after")
    def check_production_secrets(self) -> "Settings":
        """Fail closed: refuse to start a production instance that cannot
        verify sign-ins or would run half-configured payments. Every other
        environment (development/testing/staging) is intentionally left
        alone so this never affects local dev or CI."""
        if not self.is_production:
            return self

        problems: list[str] = []
        if not self.FIREBASE_PROJECT_ID:
            problems.append("FIREBASE_PROJECT_ID is empty (no sign-in could ever be verified)")
        if self.RAZORPAY_KEY_ID and not (self.RAZORPAY_KEY_SECRET and self.RAZORPAY_WEBHOOK_SECRET):
            # Half-configured Razorpay would accept payments whose webhooks
            # can never be verified (or can't call the API at all).
            problems.append(
                "RAZORPAY_KEY_ID is set but RAZORPAY_KEY_SECRET and/or RAZORPAY_WEBHOOK_SECRET is empty"
            )
        if self.DELIVERY_OTP_ENFORCED and len(self.DELIVERY_OTP_SECRET) < 32:
            problems.append(
                "DELIVERY_OTP_SECRET must be at least 32 characters while DELIVERY_OTP_ENFORCED is true "
                "(it keys the delivery-OTP hash; without it a leaked table could be brute-forced)"
            )
        if problems:
            raise ValueError(
                "Refusing to start with APP_ENV=production: " + "; ".join(problems) + ". "
                "Set them via environment variables/secret manager."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
