from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


# Configure synchronous SQLAlchemy 2 engine with psycopg 3
def _server_options() -> str:
    """libpq `options`: server-side guards so a stuck query or a forgotten open
    transaction can never hold a pooled connection (or row locks) forever."""
    parts = []
    if settings.DB_STATEMENT_TIMEOUT_MS > 0:
        parts.append(f"-c statement_timeout={int(settings.DB_STATEMENT_TIMEOUT_MS)}")
    if settings.DB_IDLE_IN_TRANSACTION_TIMEOUT_MS > 0:
        parts.append(
            f"-c idle_in_transaction_session_timeout={int(settings.DB_IDLE_IN_TRANSACTION_TIMEOUT_MS)}"
        )
    return " ".join(parts)


_connect_args = {"options": _server_options()} if _server_options() else {}

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    connect_args=_connect_args,
    echo=settings.DEBUG and not settings.is_production,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
