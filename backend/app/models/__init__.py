"""Domain models package.

Exposes Domain 1 (Identity & Access Management) SQLAlchemy models
so that Base.metadata contains all table definitions.
"""

from app.models.address import Address
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole

__all__ = ["Address", "Role", "User", "UserRole"]
