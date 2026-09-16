import json
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Every placeholder secret value that ships in source (this file and
# docker-compose.yml both define their own dev fallback strings) - if
# APP_ENV=production is ever set while one of these is still active, the
# JWT signing key or webhook secret is public knowledge to anyone who has
# read this repository. Startup fails closed rather than silently running
# with a forgeable secret in production - see Settings.check_production_secrets.
_KNOWN_PLACEHOLDER_SECRETS = {
    "dev-secret-key-replace-in-production-min-32-chars",
    "dev-container-secret-key-32chars-min",
    "dev-pnb-webhook-secret-placeholder-min-32-chars",
}


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

    # Security
    JWT_SECRET_KEY: str = "dev-secret-key-replace-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "gawachabazaar"
    JWT_AUDIENCE: str = "gawachabazaar:api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/gawachabazaar"
    )

    # PNB payment gateway (Phase 14) - placeholder values only. No real PNB
    # merchant integration specification exists yet; see
    # docs/architecture/PHASE_14_PAYMENTS.md - PNB Integration Boundary.
    # PNBGateway.initiate_payment/query_status raise NotImplementedError
    # regardless of these values until rewritten against the real contract.
    PNB_MERCHANT_ID: str = "dev-pnb-merchant-id-placeholder"
    PNB_WEBHOOK_SECRET: str = "dev-pnb-webhook-secret-placeholder-min-32-chars"
    PNB_BASE_URL: str = "https://pnb-uat.example.invalid"
    PNB_TIMEOUT_SECONDS: float = 10.0

    # Cloudinary (image uploads). Empty string means "not configured" -
    # ImageUploadService raises a clear, honest error rather than silently
    # failing if an upload route is ever called before these are set,
    # same "don't fabricate a working integration" precedent as
    # PaymentGateway/NotificationGateway.
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

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
        """Fail closed: refuse to start with a known-placeholder or
        too-short secret when APP_ENV=production. This is the single
        deployment mistake with the worst consequence in this codebase -
        a public default JWT_SECRET_KEY lets anyone forge a valid access
        token for any user, including ADMIN. Every other environment
        (development/testing/staging) is intentionally left alone so this
        never affects local dev or CI."""
        if not self.is_production:
            return self

        problems: list[str] = []
        if self.JWT_SECRET_KEY in _KNOWN_PLACEHOLDER_SECRETS or len(self.JWT_SECRET_KEY) < 32:
            problems.append("JWT_SECRET_KEY is a known placeholder or shorter than 32 characters")
        if self.PNB_WEBHOOK_SECRET in _KNOWN_PLACEHOLDER_SECRETS or len(self.PNB_WEBHOOK_SECRET) < 32:
            problems.append("PNB_WEBHOOK_SECRET is a known placeholder or shorter than 32 characters")
        if problems:
            raise ValueError(
                "Refusing to start with APP_ENV=production: " + "; ".join(problems) + ". "
                "Set real, unique, high-entropy secrets via environment variables/secret manager."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
