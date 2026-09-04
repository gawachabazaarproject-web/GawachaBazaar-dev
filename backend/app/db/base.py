"""SQLAlchemy 2 DeclarativeBase foundation.

No business domain models or premature mixins are defined here.
Domain entities and shared conventions will be added in the database architecture review phase.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass
