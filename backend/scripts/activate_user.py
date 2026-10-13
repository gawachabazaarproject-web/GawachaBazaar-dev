"""Operator CLI: set a locked-out account back to ACTIVE.

    python scripts/activate_user.py --email owner@example.com

For when the only ADMIN was deactivated or suspended and nobody is left
who can undo it from the Admin panel. The change is recorded in
admin_action_logs as coming from this CLI.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import normalize_email
from app.db.session import SessionLocal, engine
from app.models.user import User
from app.services.admin_audit import AdminAuditService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    engine.echo = False

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == normalize_email(args.email)).first()
        if user is None:
            sys.exit(f"No account with email {args.email} in database '{engine.url.database}'.")
        if user.status == "ACTIVE":
            print(f"{user.email} is already ACTIVE - nothing to do.")
            return

        previous = user.status
        user.status = "ACTIVE"
        AdminAuditService(db).record(
            admin_user_id=user.id,
            action="staff.status.update",
            resource_type="user",
            resource_id=user.id,
            previous_state=previous,
            new_state="ACTIVE",
            reason="reactivated via scripts/activate_user.py (server CLI)",
        )
        db.commit()
        print(f"{user.email} (user id {user.id}): {previous} -> ACTIVE.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
