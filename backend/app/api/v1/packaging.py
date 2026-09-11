"""Packaging domain routes: internal staff only (ADMIN, HUB_STAFF, OPERATIONS).

There is no public packaging API. CUSTOMER, WHOLESALER, and DELIVERY_PARTNER
have no access to any route in this file.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.roles import ADMIN, HUB_STAFF, OPERATIONS
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.packaging import (
    MAX_PAGE_SIZE,
    CreatePackagingInputRequest,
    CreatePackagingOperationRequest,
    CreatePackagingOutputRequest,
    PackagingInputResponse,
    PackagingOperationDetailResponse,
    PackagingOperationListResponse,
    PackagingOperationResponse,
    PackagingOutputResponse,
)
from app.services.packaging import PackagingService

router = APIRouter(dependencies=[Depends(require_roles(ADMIN, HUB_STAFF, OPERATIONS))])


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


@router.post(
    "/operations",
    response_model=PackagingOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a packaging operation (DRAFT)",
)
def create_operation(
    payload: CreatePackagingOperationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PackagingOperationResponse:
    return PackagingService(db).create_operation(payload, current_user.id)


@router.get(
    "/operations",
    response_model=PackagingOperationListResponse,
    summary="List packaging operations",
)
def list_operations(
    status_: str | None = Query(default=None, alias="status"),
    location_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> PackagingOperationListResponse:
    return PackagingService(db).list_operations(status_, location_id, page, page_size)


@router.get(
    "/operations/{operation_id}",
    response_model=PackagingOperationDetailResponse,
    summary="Get a packaging operation with its inputs and outputs",
)
def get_operation(
    operation_id: int, db: Session = Depends(get_db)
) -> PackagingOperationDetailResponse:
    return PackagingService(db).get_operation_detail(operation_id)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@router.post(
    "/operations/{operation_id}/start",
    response_model=PackagingOperationResponse,
    summary="Transition DRAFT -> IN_PROGRESS",
)
def start_operation(
    operation_id: int, db: Session = Depends(get_db)
) -> PackagingOperationResponse:
    return PackagingService(db).start_operation(operation_id)


@router.post(
    "/operations/{operation_id}/cancel",
    response_model=PackagingOperationResponse,
    summary="Transition DRAFT or IN_PROGRESS -> CANCELLED",
)
def cancel_operation(
    operation_id: int, db: Session = Depends(get_db)
) -> PackagingOperationResponse:
    return PackagingService(db).cancel_operation(operation_id)


@router.post(
    "/operations/{operation_id}/complete",
    response_model=PackagingOperationDetailResponse,
    summary="Atomically consume inputs, produce outputs, and complete the operation",
)
def complete_operation(
    operation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PackagingOperationDetailResponse:
    return PackagingService(db).complete_operation(operation_id, current_user.id)


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@router.post(
    "/operations/{operation_id}/inputs",
    response_model=PackagingInputResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a source inventory lot consumed by this operation",
)
def add_input(
    operation_id: int,
    payload: CreatePackagingInputRequest,
    db: Session = Depends(get_db),
) -> PackagingInputResponse:
    return PackagingService(db).add_input(operation_id, payload)


@router.delete(
    "/operations/{operation_id}/inputs/{input_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a recorded input (only while DRAFT/IN_PROGRESS)",
)
def remove_input(
    operation_id: int, input_id: int, db: Session = Depends(get_db)
) -> None:
    PackagingService(db).remove_input(operation_id, input_id)


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@router.post(
    "/operations/{operation_id}/outputs",
    response_model=PackagingOutputResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Declare a packaged output (resolves/creates its inventory lot)",
)
def add_output(
    operation_id: int,
    payload: CreatePackagingOutputRequest,
    db: Session = Depends(get_db),
) -> PackagingOutputResponse:
    return PackagingService(db).add_output(operation_id, payload)


@router.delete(
    "/operations/{operation_id}/outputs/{output_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a recorded output (only while DRAFT/IN_PROGRESS)",
)
def remove_output(
    operation_id: int, output_id: int, db: Session = Depends(get_db)
) -> None:
    PackagingService(db).remove_output(operation_id, output_id)
