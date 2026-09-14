"""Address domain service: a customer's own address book.

Phase 19 finding: `Address` (model, table, and the partial unique index
enforcing at most one is_default=true row per user) has existed since
Phase 1, but no service/schema/router ever exposed it - a customer had no
way to create an address through the API at all, which meant checkout
(which requires an existing address_id) was unreachable for a real
frontend. This is the minimal service layer closing that gap: plain
ownership-scoped CRUD, no new abstractions, no new tables.

TRANSACTION DESIGN: same rule as every other CUSTOMER-facing service in
this codebase - routes are protected by `require_roles`, which composes
`get_current_user` and therefore always autobegins the transaction. No
method here calls `db.begin()`.

DEFAULT ADDRESS: the partial unique index (`is_default = true`) means only
one address per user may be the default at a time. Setting a NEW address
as default therefore first unsets whichever one currently holds it, in
the same transaction - never relying on the database to reject a second
default and surface a confusing IntegrityError. A user's very first
address is always forced to be the default, so checkout has a sensible
address to preselect without an extra step.

Deleting an address never touches historical orders: `OrderAddress`
(app/models/order_address.py) is a full field-by-field snapshot taken at
checkout time with no foreign key back to `addresses` - removing an
address from a customer's book cannot corrupt or orphan any past order.
"""

from sqlalchemy.orm import Session

from app.exceptions.base import NotFoundError
from app.models.address import Address
from app.schemas.address import (
    AddressListResponse,
    AddressResponse,
    CreateAddressRequest,
    UpdateAddressRequest,
)


class AddressService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_addresses(self, user_id: int) -> AddressListResponse:
        items = (
            self.db.query(Address)
            .filter(Address.user_id == user_id)
            .order_by(Address.is_default.desc(), Address.id.desc())
            .all()
        )
        return AddressListResponse(
            items=[AddressResponse.model_validate(a) for a in items]
        )

    def get_address(self, user_id: int, address_id: int) -> AddressResponse:
        address = self._get_owned_address(user_id, address_id)
        return AddressResponse.model_validate(address)

    def create_address(self, user_id: int, data: CreateAddressRequest) -> AddressResponse:
        is_first = (
            self.db.query(Address).filter(Address.user_id == user_id).first() is None
        )
        make_default = data.is_default or is_first

        if make_default:
            self._unset_current_default(user_id)

        address = Address(
            user_id=user_id,
            label=data.label,
            address_line_1=data.address_line_1,
            address_line_2=data.address_line_2,
            city=data.city,
            state=data.state,
            postal_code=data.postal_code,
            latitude=data.latitude,
            longitude=data.longitude,
            is_default=make_default,
        )
        self.db.add(address)
        self.db.commit()
        self.db.refresh(address)
        return AddressResponse.model_validate(address)

    def update_address(
        self, user_id: int, address_id: int, data: UpdateAddressRequest
    ) -> AddressResponse:
        address = self._get_owned_address(user_id, address_id)
        update_data = data.model_dump(exclude_unset=True)

        if update_data.get("is_default") is True:
            self._unset_current_default(user_id, exclude_address_id=address.id)
        elif update_data.get("is_default") is False and address.is_default:
            # An address may not un-default itself with nothing else made
            # default - a customer always has exactly one default once
            # they have at least one address, so checkout always has a
            # sensible preselection.
            update_data.pop("is_default")

        for field, value in update_data.items():
            setattr(address, field, value)

        self.db.commit()
        self.db.refresh(address)
        return AddressResponse.model_validate(address)

    def delete_address(self, user_id: int, address_id: int) -> None:
        address = self._get_owned_address(user_id, address_id)
        was_default = address.is_default
        self.db.delete(address)
        self.db.flush()

        if was_default:
            # Promote the customer's next-most-recent remaining address
            # (if any) so checkout always has a default to preselect.
            fallback = (
                self.db.query(Address)
                .filter(Address.user_id == user_id)
                .order_by(Address.id.desc())
                .first()
            )
            if fallback is not None:
                fallback.is_default = True

        self.db.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_owned_address(self, user_id: int, address_id: int) -> Address:
        address = (
            self.db.query(Address)
            .filter(Address.id == address_id, Address.user_id == user_id)
            .first()
        )
        if address is None:
            # Never distinguish "doesn't exist" from "belongs to someone
            # else" - both are 404, matching this codebase's established
            # convention (see PaymentService._get_owned_payment).
            raise NotFoundError("Address not found.")
        return address

    def _unset_current_default(
        self, user_id: int, *, exclude_address_id: int | None = None
    ) -> None:
        query = self.db.query(Address).filter(
            Address.user_id == user_id, Address.is_default.is_(True)
        )
        if exclude_address_id is not None:
            query = query.filter(Address.id != exclude_address_id)
        current_default = query.first()
        if current_default is not None:
            current_default.is_default = False
            self.db.flush()
