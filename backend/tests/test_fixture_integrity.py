"""Guards the test fixtures themselves (not the application)."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError


def test_db_session_fixture_does_not_hold_locks_on_other_connections(test_engine, db_session) -> None:
    """Regression: the fixture's TRUNCATE must really be committed. If the
    Session joins an outer, never-committed connection transaction, it keeps
    ACCESS EXCLUSIVE locks and every other connection (the app's `get_db`
    override uses one) blocks for the rest of the test."""
    with test_engine.connect() as other:
        other.execute(text("SET lock_timeout = '2s'"))
        try:
            assert other.execute(text("SELECT count(*) FROM users")).scalar() == 0
            assert other.execute(text("SELECT count(*) FROM inventory_reservations")).scalar() == 0
        except OperationalError as exc:  # pragma: no cover - failure path
            pytest.fail(f"another connection is blocked by the db_session fixture: {exc}")
