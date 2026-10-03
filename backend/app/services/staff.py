"""Admin-panel staff/employee management.

A "staff member" is any User holding at least one role in STAFF_ROLES
(app/core/roles.py) - ADMIN, HUB_STAFF, OPERATIONS, DELIVERY_PARTNER,
SUPPORT - not a separate table, mirroring how "customer" already means "a
User holding the CUSTOMER role" (see CustomerService). Multiple roles per
user are already a first-class case in the schema (UserRole has no
one-role-per-user constraint, only a partial unique index on
`is_primary`) - granting a staff role here never touches or removes
whatever non-staff role (e.g. CUSTOMER) a user already has.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.firebase import (
    FirebaseEmailExistsError,
    FirebasePasswordRejectedError,
    FirebaseUnavailableError,
    get_firebase,
)
from app.core.roles import STAFF_ROLES
from app.exceptions.base import (
    AppException,
    BusinessValidationError,
    ConflictError,
    NotFoundError,
)
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.staff import (
    CreateStaffRequest,
    StaffDetailResponse,
    StaffListItemResponse,
)
from app.services.admin_audit import AdminAuditService


class StaffService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def admin_list_staff(self) -> list[StaffListItemResponse]:
        users = (
            self.db.query(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .filter(Role.name.in_(STAFF_ROLES))
            .options(joinedload(User.user_roles).joinedload(UserRole.role))
            .distinct()
            .order_by(User.created_at.desc())
            .all()
        )
        return [self._to_list_item(u) for u in users]

    def admin_get_staff_detail(self, user_id: int) -> StaffDetailResponse:
        user = self._get_staff_or_404(user_id)
        item = self._to_list_item(user)
        return StaffDetailResponse(**item.model_dump(), updated_at=user.updated_at)

    def admin_create_staff(
        self, data: CreateStaffRequest, admin_user_id: int
    ) -> StaffDetailResponse:
        role = self._require_staff_role(data.role)

        taken = (
            self.db.query(User.id)
            .filter((User.email == data.email) | (User.phone == data.phone))
            .first()
        )
        if taken:
            raise ConflictError("A user with this email or phone already exists.")

        # Firebase holds the credential; the admin-entered email counts as
        # verified so the new staff member can sign in straight away.
        firebase = get_firebase()
        try:
            uid = firebase.create_user(
                email=data.email, password=data.password, display_name=data.name, email_verified=True
            )
        except FirebaseEmailExistsError as exc:
            raise ConflictError("A sign-in account with this email already exists.") from exc
        except FirebasePasswordRejectedError as exc:
            raise BusinessValidationError("Password does not meet the password policy.") from exc
        except FirebaseUnavailableError as exc:
            raise AppException(
                "Creating staff accounts is temporarily unavailable.", status_code=503, code="AUTH_UNAVAILABLE"
            ) from exc

        try:
            user = User(
                firebase_uid=uid,
                name=data.name,
                email=data.email,
                phone=data.phone,
                status="ACTIVE",
            )
            self.db.add(user)
            self.db.flush()
            self.db.add(UserRole(user_id=user.id, role_id=role.id, is_primary=True))
            AdminAuditService(self.db).record(
                admin_user_id=admin_user_id,
                action="staff.create",
                resource_type="user",
                resource_id=user.id,
                new_state=data.role,
                reason=f"email={data.email}",
            )
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            firebase.delete_user(uid)  # no orphaned sign-in without an app user
            if isinstance(exc, IntegrityError):
                raise ConflictError("A user with this email or phone already exists.") from exc
            raise

        return self.admin_get_staff_detail(user.id)

    def admin_assign_role(
        self, user_id: int, role_name: str, admin_user_id: int
    ) -> StaffDetailResponse:
        role = self._require_staff_role(role_name)
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundError("User not found.")

        existing = (
            self.db.query(UserRole)
            .filter(UserRole.user_id == user_id, UserRole.role_id == role.id)
            .first()
        )
        if existing:
            return self.admin_get_staff_detail(user_id)  # idempotent - already granted

        has_primary = (
            self.db.query(UserRole)
            .filter(UserRole.user_id == user_id, UserRole.is_primary.is_(True))
            .first()
        )
        self.db.add(
            UserRole(user_id=user_id, role_id=role.id, is_primary=has_primary is None)
        )
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="staff.role.assign",
            resource_type="user",
            resource_id=user_id,
            new_state=role_name,
        )
        self.db.commit()
        return self.admin_get_staff_detail(user_id)

    def admin_revoke_role(
        self, user_id: int, role_name: str, admin_user_id: int
    ) -> StaffDetailResponse:
        role = self._require_staff_role(role_name)
        user_role = (
            self.db.query(UserRole)
            .filter(UserRole.user_id == user_id, UserRole.role_id == role.id)
            .first()
        )
        if not user_role:
            raise NotFoundError("This user does not hold that role.")

        remaining = (
            self.db.query(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .filter(
                UserRole.user_id == user_id,
                Role.name.in_(STAFF_ROLES),
                UserRole.id != user_role.id,
            )
            .count()
        )
        if remaining == 0:
            raise BusinessValidationError(
                "Cannot remove a staff member's last staff role - deactivate the "
                "account instead."
            )

        was_primary = user_role.is_primary
        self.db.delete(user_role)
        self.db.flush()
        if was_primary:
            # The partial unique index on `is_primary=true` never wants zero
            # rows for a user who still holds roles - promote any remaining
            # one. Nothing else in the codebase reads *which* role is
            # primary, only that exactly one is.
            fallback = self.db.query(UserRole).filter(UserRole.user_id == user_id).first()
            if fallback:
                fallback.is_primary = True

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="staff.role.revoke",
            resource_type="user",
            resource_id=user_id,
            previous_state=role_name,
        )
        self.db.commit()
        return self.admin_get_staff_detail(user_id)

    def admin_set_status(
        self, user_id: int, new_status: str, admin_user_id: int
    ) -> StaffDetailResponse:
        if new_status not in ("ACTIVE", "INACTIVE", "SUSPENDED"):
            raise BusinessValidationError(f"Invalid status '{new_status}'.")
        user = self._get_staff_or_404(user_id)
        previous = user.status
        user.status = new_status
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="staff.status.update",
            resource_type="user",
            resource_id=user_id,
            previous_state=previous,
            new_state=new_status,
        )
        self.db.commit()
        return self.admin_get_staff_detail(user_id)

    # ------------------------------------------------------------------
    def _require_staff_role(self, role_name: str) -> Role:
        if role_name not in STAFF_ROLES:
            raise BusinessValidationError(
                f"'{role_name}' is not a staff role. Must be one of: "
                f"{', '.join(sorted(STAFF_ROLES))}."
            )
        role = self.db.query(Role).filter_by(name=role_name).first()
        if not role:
            raise BusinessValidationError(f"Role '{role_name}' does not exist.")
        return role

    def _get_staff_or_404(self, user_id: int) -> User:
        user = (
            self.db.query(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .filter(User.id == user_id, Role.name.in_(STAFF_ROLES))
            .options(joinedload(User.user_roles).joinedload(UserRole.role))
            .first()
        )
        if not user:
            raise NotFoundError("Staff member not found.")
        return user

    @staticmethod
    def _to_list_item(user: User) -> StaffListItemResponse:
        roles = sorted({ur.role.name for ur in user.user_roles if ur.role.name in STAFF_ROLES})
        return StaffListItemResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone,
            status=user.status,
            roles=roles,
            created_at=user.created_at,
        )
