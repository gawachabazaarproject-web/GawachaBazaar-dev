"""Domain models package.

Exposes Phase 1 (Identity & Access) and Phase 2 (Farm & Traceability)
SQLAlchemy models so that Base.metadata contains all table definitions.
"""

from app.models.address import Address
from app.models.batch import Batch
from app.models.farm import Farm
from app.models.quality_check import QualityCheck
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole

__all__ = [
    "Address",
    "Batch",
    "Farm",
    "QualityCheck",
    "Role",
    "User",
    "UserRole",
]
