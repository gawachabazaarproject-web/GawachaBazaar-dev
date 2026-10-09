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
    # single secret env value (Render secret) - never commit it. When it is
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
    # DELIVERY_BASE_FEE + DELIVERY_PER_KM per km of straight-line distance
    # from the packing point to the delivery address (distance counted up
    # to DELIVERY_MAX_CHARGED_KM, so one bad coordinate can never produce a
    # absurd fee). PACKING_POINT_LATITUDE/LONGITUDE must be set for the
    # per-km part to apply; without them (or without GPS on the address)
    # only the base fee is charged. A customer with BAZAAR_PLUS_ORDERS_REQUIRED
    # Bazaar orders (each with >= FREE_DELIVERY_MIN_ITEMS different products)
    # in the current calendar month (BAZAAR_TIMEZONE) is eligible for
    # Gawacha Bazaar+.
    FREE_DELIVERY_MIN_ITEMS: int = 15
    DELIVERY_BASE_FEE: Decimal = Decimal("20")
    DELIVERY_PER_KM: Decimal = Decimal("10")
    DELIVERY_MAX_CHARGED_KM: float = 30.0
    PACKING_POINT_LATITUDE: float | None = None
    PACKING_POINT_LONGITUDE: float | None = None
    BAZAAR_PLUS_ORDERS_REQUIRED: int = 6
    BAZAAR_TIMEZONE: str = "Asia/Kolkata"

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
