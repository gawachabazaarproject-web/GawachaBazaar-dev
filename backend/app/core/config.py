import json
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
