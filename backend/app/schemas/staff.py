"""Admin-panel staff/employee management schemas.

A "staff member" is any User holding at least one role in STAFF_ROLES
(app/core/roles.py) - not a separate table, mirroring how "customer"
already means "a User holding the CUSTOMER role" (see
app/services/customer.py).
"""

from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.core.security import normalize_email, normalize_phone
from app.schemas.base import BaseSchema


class StaffListItemResponse(BaseSchema):
    id: int
    name: str
    email: str | None = None
    phone: str | None = None
    status: str
    roles: list[str]
    created_at: datetime


class StaffDetailResponse(StaffListItemResponse):
    updated_at: datetime


class CreateStaffRequest(BaseSchema):
    name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(..., description="One of the STAFF_ROLES names, e.g. 'HUB_STAFF'.")

    @field_validator("email", mode="after")
    @classmethod
    def validate_and_normalize_email(cls, v: EmailStr) -> str:
        return normalize_email(str(v))

    @field_validator("phone", mode="after")
    @classmethod
    def validate_and_normalize_phone(cls, v: str) -> str:
        try:
            return normalize_phone(v)
        except ValueError as e:
            raise ValueError(str(e)) from e


class AssignStaffRoleRequest(BaseSchema):
    role: str = Field(..., description="One of the STAFF_ROLES names, e.g. 'OPERATIONS'.")


class UpdateStaffStatusRequest(BaseSchema):
    status: str = Field(..., description="One of ACTIVE, INACTIVE, SUSPENDED.")
