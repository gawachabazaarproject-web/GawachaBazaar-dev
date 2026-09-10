from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped SQLAlchemy session per request.

    Guarantees session cleanup upon request completion.
    Services performing multi-write workflows control their own transaction
    boundaries explicitly.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
