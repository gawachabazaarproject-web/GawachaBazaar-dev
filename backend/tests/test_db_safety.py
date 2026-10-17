"""Proves the test-database safety policy fails closed.

None of these tests opens a database connection (the subprocess test runs
with an environment that is *expected* to be refused before any connect).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests._db_safety import (
    DISPOSABLE_MARKER,
    UNROUTABLE_SENTINEL_URL,
    UnsafeTestDatabaseError,
    resolve_test_database_url,
    verify_live_target,
)

GOOD = "postgresql+psycopg://qa_test:pw@127.0.0.1:15432/gawachabazaar_test"
BACKEND_DIR = Path(__file__).resolve().parent.parent


def _env(**kw: str) -> dict[str, str]:
    return {k: v for k, v in kw.items()}


def _loopback_resolver(*_a, **_k):
    return [(2, 1, 6, "", ("127.0.0.1", 0))]


def test_accepts_explicit_local_url() -> None:
    assert resolve_test_database_url({"TEST_DATABASE_URL": GOOD}) == GOOD


def test_accepts_ipv6_loopback_and_normalizes_driver() -> None:
    out = resolve_test_database_url({"TEST_DATABASE_URL": "postgresql://u:p@[::1]:15432/x_test"})
    assert out.startswith("postgresql+psycopg://")


def test_accepts_localhost_only_when_it_resolves_to_loopback() -> None:
    url = "postgresql+psycopg://u:p@localhost:15432/x_test"
    assert resolve_test_database_url({"TEST_DATABASE_URL": url}, resolver=_loopback_resolver)
    with pytest.raises(UnsafeTestDatabaseError, match="non-loopback"):
        resolve_test_database_url(
            {"TEST_DATABASE_URL": url},
            resolver=lambda *a, **k: [(2, 1, 6, "", ("10.1.2.3", 0))],
        )


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_or_blank_fails_closed(value) -> None:
    env = {} if value is None else {"TEST_DATABASE_URL": value}
    with pytest.raises(UnsafeTestDatabaseError, match="not set"):
        resolve_test_database_url(env)


def test_database_url_alone_is_never_used() -> None:
    """The old behaviour derived the test DB from DATABASE_URL. Now it must fail."""
    env = {"DATABASE_URL": "postgresql+psycopg://u:p@db.render.com/gawachabazaar_demo_db"}
    with pytest.raises(UnsafeTestDatabaseError, match="not set"):
        resolve_test_database_url(env)


@pytest.mark.parametrize(
    "url, fragment",
    [
        # the exact value the old string-replace produced from the Render .env
        ("postgresql+psycopg://u:p@dpg-x-a.oregon-postgres.render.com/gawachabazaar_test_demo_db", "not loopback"),
        ("postgresql+psycopg://u:p@10.0.0.5:15432/x_test", "not loopback"),
        ("postgresql+psycopg://u:p@0.0.0.0:15432/x_test", "not loopback"),
        ("postgresql+psycopg://u:p@127.0.0.1.evil.com:15432/x_test", "not loopback"),
        ("postgresql+psycopg://u:p@127.0.0.1,db.example.com:15432/x_test", "multiple hosts"),
        ("postgresql+psycopg:///x_test", "host is required"),
        ("postgresql+psycopg://u:p@127.0.0.1/x_test", "explicit port"),
        ("postgresql+psycopg://u:p@127.0.0.1:5432/x_test", "reserved"),
        ("postgresql+psycopg://u:p@127.0.0.1:5433/x_test", "reserved"),
        ("postgresql+psycopg://u:p@127.0.0.1:15432/gawachabazaar", "must match"),
        ("postgresql+psycopg://u:p@127.0.0.1:15432/gawachabazaar_test_demo_db", "must match"),
        ("postgresql+psycopg://u:p@127.0.0.1:15432/Prod_test", "must match"),
        ("postgresql+psycopg://u:p@127.0.0.1:15432/", "must match"),
        ("postgresql+psycopg://u:p@127.0.0.1:15432/x_test?host=db.render.com", "redirect"),
        ("postgresql+psycopg://u:p@127.0.0.1:15432/x_test?hostaddr=8.8.8.8", "redirect"),
        ("postgresql+psycopg://u:p@127.0.0.1:15432/x_test?service=prod", "redirect"),
        ("mysql://u:p@127.0.0.1:15432/x_test", "driver"),
        ("postgres://u:p@127.0.0.1:15432/x_test", "driver"),
        ("not a url", "valid database URL"),
    ],
)
def test_unsafe_targets_are_rejected(url: str, fragment: str) -> None:
    with pytest.raises(UnsafeTestDatabaseError, match=fragment):
        resolve_test_database_url({"TEST_DATABASE_URL": url}, resolver=_loopback_resolver)


def test_rejects_url_identical_to_database_url() -> None:
    env = {"TEST_DATABASE_URL": GOOD, "DATABASE_URL": GOOD.replace("postgresql+psycopg", "postgresql")}
    with pytest.raises(UnsafeTestDatabaseError, match="identical"):
        resolve_test_database_url(env)


class _FakeConn:
    def __init__(self, db_name, marker=DISPOSABLE_MARKER) -> None:
        self._db, self._marker = db_name, marker

    def exec_driver_sql(self, sql: str):
        value = self._marker if "shobj_description" in sql else self._db

        class _R:
            def scalar(self_inner):  # noqa: N805
                return value

        return _R()


def test_live_target_check_blocks_a_mismatched_database() -> None:
    verify_live_target(_FakeConn("gawachabazaar_test"), GOOD)  # matches + marked: no error
    with pytest.raises(UnsafeTestDatabaseError, match="does not match"):
        verify_live_target(_FakeConn("gawachabazaar_demo_db"), GOOD)
    with pytest.raises(UnsafeTestDatabaseError, match="does not match"):
        verify_live_target(_FakeConn(None), GOOD)


@pytest.mark.parametrize("marker", [None, "", "something-else"])
def test_live_target_check_requires_disposable_marker(marker) -> None:
    """A loopback port-forward to a remote *_test database has no marker."""
    with pytest.raises(UnsafeTestDatabaseError, match="not marked disposable"):
        verify_live_target(_FakeConn("gawachabazaar_test", marker), GOOD)


@pytest.mark.parametrize("var", ["PGHOSTADDR", "PGHOST", "PGSERVICE", "PGPORT", "PGOPTIONS"])
def test_libpq_environment_overrides_are_refused(var: str) -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="override the connection target"):
        resolve_test_database_url({"TEST_DATABASE_URL": GOOD, var: "203.0.113.9"})


def test_remote_host_with_valid_test_name_is_rejected() -> None:
    """Regression guard: host allow-list must be enforced on its own."""
    with pytest.raises(UnsafeTestDatabaseError, match="not loopback"):
        resolve_test_database_url({"TEST_DATABASE_URL": "postgresql+psycopg://u:p@db.render.com:15432/x_test"})


@pytest.mark.parametrize(
    "tail",
    ["?options=-c%20search_path=x", "?target_session_attrs=any", "?load_balance_hosts=random"],
)
def test_unknown_libpq_query_keys_are_refused(tail: str) -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="redirect"):
        resolve_test_database_url({"TEST_DATABASE_URL": GOOD + tail})


def test_allow_listed_query_keys_pass() -> None:
    assert resolve_test_database_url({"TEST_DATABASE_URL": GOOD + "?connect_timeout=5&sslmode=disable"})


def test_global_engine_is_pinned_to_loopback_so_app_code_cannot_reach_a_real_db() -> None:
    """App code that bypasses the get_db override (reservation sweep, push
    sends) uses app.db.session.engine; it must never point off-machine."""
    from app.db.session import engine

    assert engine.url.host in {"127.0.0.1", "localhost", "::1"}
    assert os.environ["APP_ENV"] == "testing"
    for name in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "CLOUDINARY_API_SECRET", "GOOGLE_MAPS_API_KEY"):
        assert os.environ[name] == "", f"{name} must be blank during tests"


@pytest.mark.parametrize(
    "test_url",
    [
        "",  # missing
        "postgresql+psycopg://u:p@dpg-x-a.oregon-postgres.render.com:5432/gawachabazaar_test_demo_db",  # remote
        "postgresql+psycopg://u:p@127.0.0.1:5432/gawachabazaar",  # local but unsafe name/port
    ],
)
def test_real_fixtures_refuse_unsafe_configuration_before_connecting(test_url: str) -> None:
    """Runs a fresh pytest session whose DB-backed fixtures must abort with
    UnsafeTestDatabaseError, and whose global engine is the unroutable sentinel."""
    env = {k: v for k, v in os.environ.items() if k != "TEST_DATABASE_URL"}
    env["DATABASE_URL"] = "postgresql+psycopg://u:p@dpg-x-a.oregon-postgres.render.com/gawachabazaar_demo_db"
    if test_url:
        env["TEST_DATABASE_URL"] = test_url
    proc = subprocess.run(  # noqa: S603 - fixed argv, test-only
        [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
         "tests/test_health.py::test_database_health_success"],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0
    assert "UnsafeTestDatabaseError" in out
    assert "1 passed" not in out


def test_sentinel_is_unroutable() -> None:
    assert "127.0.0.1:1/" in UNROUTABLE_SENTINEL_URL
