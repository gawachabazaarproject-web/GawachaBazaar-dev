"""Admin-panel staff/employee management - create internal accounts and
assign the operational roles that gate the rest of this admin panel.
ADMIN-only throughout (see STAFF_PERMISSIONS in app/core/permissions.py -
same precedent as Refunds/Promotions: who can act as staff, including who
can grant ADMIN itself, is at least as sensitive as a discount rule).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies.auth import require_permission
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.staff import (
    AssignStaffRoleRequest,
    CreateStaffRequest,
    StaffDetailResponse,
    StaffListItemResponse,
    UpdateStaffStatusRequest,
)
from app.services.staff import StaffService

router = APIRouter()


@router.get("", response_model=list[StaffListItemResponse], summary="List Staff")
def list_staff(
    current_user: User = Depends(require_permission("staff.read")),
    db: Session = Depends(get_db),
) -> list[StaffListItemResponse]:
    return StaffService(db).admin_list_staff()


@router.get("/{user_id}", response_model=StaffDetailResponse, summary="Get Staff Detail")
def get_staff(
    user_id: int,
    current_user: User = Depends(require_permission("staff.read")),
    db: Session = Depends(get_db),
) -> StaffDetailResponse:
    return StaffService(db).admin_get_staff_detail(user_id)


@router.post(
    "",
    response_model=StaffDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Staff Account",
)
def create_staff(
    payload: CreateStaffRequest,
    current_user: User = Depends(require_permission("staff.manage")),
    db: Session = Depends(get_db),
) -> StaffDetailResponse:
    return StaffService(db).admin_create_staff(payload, current_user.id)


@router.post(
    "/{user_id}/roles",
    response_model=StaffDetailResponse,
    summary="Assign Staff Role",
)
def assign_role(
    user_id: int,
    payload: AssignStaffRoleRequest,
    current_user: User = Depends(require_permission("staff.manage")),
    db: Session = Depends(get_db),
) -> StaffDetailResponse:
    return StaffService(db).admin_assign_role(user_id, payload.role, current_user.id)


@router.delete(
    "/{user_id}/roles/{role_name}",
    response_model=StaffDetailResponse,
    summary="Revoke Staff Role",
)
def revoke_role(
    user_id: int,
    role_name: str,
    current_user: User = Depends(require_permission("staff.manage")),
    db: Session = Depends(get_db),
) -> StaffDetailResponse:
    return StaffService(db).admin_revoke_role(user_id, role_name, current_user.id)


@router.patch(
    "/{user_id}/status",
    response_model=StaffDetailResponse,
    summary="Set Staff Account Status",
)
def set_status(
    user_id: int,
    payload: UpdateStaffStatusRequest,
    current_user: User = Depends(require_permission("staff.manage")),
    db: Session = Depends(get_db),
) -> StaffDetailResponse:
    return StaffService(db).admin_set_status(user_id, payload.status, current_user.id)
