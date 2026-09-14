"""Address domain routes: CUSTOMER-only, always scoped to the authenticated
user's own address book. See app/services/address.py for why this exists
(Phase 19 finding - checkout requires an address_id, and there was
previously no API path to ever create one).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.roles import CUSTOMER
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.address import (
    AddressListResponse,
    AddressResponse,
    CreateAddressRequest,
    UpdateAddressRequest,
)
from app.services.address import AddressService

router = APIRouter(dependencies=[Depends(require_roles(CUSTOMER))])


@router.get("", response_model=AddressListResponse, summary="List the current user's addresses")
def list_addresses(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AddressListResponse:
    return AddressService(db).list_addresses(current_user.id)


@router.post(
    "",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new address to the current user's address book",
)
def create_address(
    payload: CreateAddressRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AddressResponse:
    return AddressService(db).create_address(current_user.id, payload)


@router.get(
    "/{address_id}",
    response_model=AddressResponse,
    summary="Get one of the current user's addresses",
)
def get_address(
    address_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AddressResponse:
    return AddressService(db).get_address(current_user.id, address_id)


@router.patch(
    "/{address_id}",
    response_model=AddressResponse,
    summary="Update one of the current user's addresses",
)
def update_address(
    address_id: int,
    payload: UpdateAddressRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AddressResponse:
    return AddressService(db).update_address(current_user.id, address_id, payload)


@router.delete(
    "/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of the current user's addresses",
)
def delete_address(
    address_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    AddressService(db).delete_address(current_user.id, address_id)
