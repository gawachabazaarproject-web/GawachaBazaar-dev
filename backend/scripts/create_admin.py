"""Operator CLI: create the first ADMIN account on a fresh database.

The baseline-roles migration (37bbdf459894) seeds `roles` but deliberately
creates no users (see docs/architecture/PHASE_9_RBAC.md §2), and every
staff-management route requires an existing ADMIN - so a freshly deployed
production database has no way to reach the Admin panel at all without
this. Run it once, on the server, after `alembic upgrade head`:

    docker compose --env-file .env.production -f docker-compose.prod.yml \
        run --rm backend python scripts/create_admin.py \
        --name "Owner Name" --email owner@example.com --phone 9876543210

The password is prompted for interactively (never passed as an argument,
so it never lands in shell history or `ps` output). Input goes through the
same CreateStaffRequest schema the Admin panel's own "create staff" route
uses, so email/phone normalization and password rules are identical.

If the email already belongs to an existing user, ADMIN is granted to that
account instead (no password change). Either way an admin_action_logs row
records that the grant came from this CLI, not the panel.
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.roles import ADMIN
from app.core.security import hash_password, normalize_email
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.staff import CreateStaffRequest
from app.services.admin_audit import AdminAuditService


def _read_password() -> str:
    password = getpass.getpass("Password for the new ADMIN (min 8 chars): ")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--phone", required=True)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        admin_role = db.query(Role).filter(Role.name == ADMIN).first()
        if admin_role is None:
            sys.exit("ADMIN role missing - run `alembic upgrade head` first.")

        existing = db.query(User).filter(User.email == normalize_email(args.email)).first()
        if existing is not None:
            already = (
                db.query(UserRole)
                .filter(UserRole.user_id == existing.id, UserRole.role_id == admin_role.id)
                .first()
            )
            if already:
                print(f"{existing.email} already has ADMIN - nothing to do.")
                return
            has_primary = (
                db.query(UserRole)
                .filter(UserRole.user_id == existing.id, UserRole.is_primary.is_(True))
                .first()
            )
            db.add(UserRole(user_id=existing.id, role_id=admin_role.id, is_primary=has_primary is None))
            user = existing
            action = "staff.role.assign"
        else:
            try:
                data = CreateStaffRequest(
                    name=args.name,
                    email=args.email,
                    phone=args.phone,
                    password=_read_password(),
                    role=ADMIN,
                )
            except ValidationError as exc:
                sys.exit(f"Invalid input:\n{exc}")

            user = User(
                name=data.name,
                email=data.email,
                phone=data.phone,
                password_hash=hash_password(data.password),
                status="ACTIVE",
            )
            db.add(user)
            db.flush()
            db.add(UserRole(user_id=user.id, role_id=admin_role.id, is_primary=True))
            action = "staff.create"

        AdminAuditService(db).record(
            admin_user_id=user.id,
            action=action,
            resource_type="user",
            resource_id=user.id,
            new_state=ADMIN,
            reason="bootstrap via scripts/create_admin.py (server CLI)",
        )
        db.commit()
        print(f"ADMIN ready: {user.email} (user id {user.id}).")
    except IntegrityError:
        db.rollback()
        sys.exit("A user with this email or phone already exists.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
