"""Operator CLI: read-only check of one account's sign-in state.

    python scripts/check_admin.py --email owner@example.com

Prints whether the row is linked to a Firebase user, whether it still has a
pre-Firebase password, and its roles. Changes nothing.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import normalize_email
from app.db.session import SessionLocal, engine
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    engine.echo = False

    db = SessionLocal()
    try:
        print(f"database host : {engine.url.host}")
        print(f"database name : {engine.url.database}")
        print(f"total users   : {db.query(User).count()}")
        user = db.query(User).filter(User.email == normalize_email(args.email)).first()
        if user is None:
            print("account       : NOT FOUND in this database")
            return
        roles = (
            db.query(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user.id)
            .all()
        )
        print(f"user id       : {user.id}")
        print(f"status        : {user.status}")
        print(f"roles         : {sorted(name for (name,) in roles)}")
        print(f"firebase uid  : {user.firebase_uid or '(not linked)'}")
        print(f"legacy pw set : {user.password_hash is not None}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
