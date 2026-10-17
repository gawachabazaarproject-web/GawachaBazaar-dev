"""Fail-closed safety policy for the database the test-suite may destroy.

The suite TRUNCATEs ~50 tables between tests, so the target must be provably
a disposable, local database. Nothing here is derived from DATABASE_URL (which
points at real environments in developer `.env` files): the target must be
given explicitly through TEST_DATABASE_URL and must pass every rule below.

Rules (all must hold):
  * TEST_DATABASE_URL is set and non-empty
  * driver is postgresql / postgresql+psycopg
  * exactly one host, and it is 127.0.0.1, localhost or ::1
    ("localhost" must also resolve only to loopback addresses)
  * an explicit port, not 5432/5433 (the usual local dev / compose ports)
  * database name matches ^[a-z][a-z0-9_]*_test$
  * only allow-listed query keys (connect_timeout, application_name, sslmode)
  * no PGHOST/PGHOSTADDR/PGPORT/PGDATABASE/PGSERVICE/... environment overrides
  * the database carries the disposable marker comment (checked after connecting)
  * the URL is not identical to DATABASE_URL
After connecting, `verify_live_target` re-checks `current_database()` before
any destructive SQL runs.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable, Mapping

from sqlalchemy.engine import URL, make_url

ENV_VAR = "TEST_DATABASE_URL"

# Used when the configuration is missing/unsafe: an address nothing listens on,
# so any code path that ignores the fixtures still cannot reach a real DB.
UNROUTABLE_SENTINEL_URL = "postgresql+psycopg://unsafe:unsafe@127.0.0.1:1/unconfigured_test"

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_FORBIDDEN_PORTS = frozenset({5432, 5433})
_ALLOWED_DRIVERS = frozenset({"postgresql", "postgresql+psycopg"})
_DB_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*_test$")
# Allow-list: any other libpq key (host, hostaddr, port, service, options, ...)
# could redirect or reconfigure the connection and is refused.
_ALLOWED_QUERY_KEYS = frozenset({"connect_timeout", "application_name", "sslmode"})
# libpq environment variables that override the host/target even when the URL
# is explicit (e.g. PGHOSTADDR). Their presence is ambiguous -> fail closed.
_FORBIDDEN_ENV_VARS = (
    "PGHOST", "PGHOSTADDR", "PGPORT", "PGDATABASE", "PGSERVICE",
    "PGSERVICEFILE", "PGPASSFILE", "PGOPTIONS",
)
# Comment that must be set on the database itself (COMMENT ON DATABASE ...).
# A loopback port-forward to a remote DB would not carry it.
DISPOSABLE_MARKER = "gb-disposable-test-db"


class UnsafeTestDatabaseError(RuntimeError):
    """The configured test database is missing, remote or ambiguous."""


def _normalize(url: URL) -> str:
    return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


def resolve_test_database_url(
    env: Mapping[str, str],
    resolver: Callable[..., list] = socket.getaddrinfo,
) -> str:
    """Return a validated, normalised test DB URL or raise UnsafeTestDatabaseError.

    Never opens a connection.
    """
    raw = (env.get(ENV_VAR) or "").strip()
    if not raw:
        raise UnsafeTestDatabaseError(
            f"{ENV_VAR} is not set. Refusing to run: the suite truncates tables and must be "
            "pointed explicitly at a disposable local database, e.g. "
            "postgresql+psycopg://user:pw@127.0.0.1:15432/gawachabazaar_test"
        )
    try:
        url = make_url(raw)
    except Exception as exc:  # noqa: BLE001 - any parse failure is unsafe
        raise UnsafeTestDatabaseError(f"{ENV_VAR} is not a valid database URL.") from exc

    if url.drivername not in _ALLOWED_DRIVERS:
        raise UnsafeTestDatabaseError(f"{ENV_VAR}: driver {url.drivername!r} is not allowed.")

    host = url.host
    if not host:
        raise UnsafeTestDatabaseError(f"{ENV_VAR}: a host is required (unix sockets are not allowed).")
    if "," in host:
        raise UnsafeTestDatabaseError(f"{ENV_VAR}: multiple hosts are not allowed.")
    if host.lower() not in _LOOPBACK_HOSTS:
        raise UnsafeTestDatabaseError(
            f"{ENV_VAR}: host {host!r} is not loopback. Tests only run against 127.0.0.1/localhost/::1."
        )
    if host.lower() == "localhost":
        try:
            infos = resolver("localhost", url.port or 0, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise UnsafeTestDatabaseError("'localhost' could not be resolved.") from exc
        addrs = {info[4][0] for info in infos}
        if not addrs or not all(ipaddress.ip_address(a.split("%")[0]).is_loopback for a in addrs):
            raise UnsafeTestDatabaseError(f"'localhost' resolves to non-loopback address(es): {sorted(addrs)}")

    if url.port is None:
        raise UnsafeTestDatabaseError(f"{ENV_VAR}: an explicit port is required.")
    if url.port in _FORBIDDEN_PORTS:
        raise UnsafeTestDatabaseError(
            f"{ENV_VAR}: port {url.port} is reserved for local dev databases; use a dedicated test port."
        )

    if not url.database or not _DB_NAME_RE.fullmatch(url.database):
        raise UnsafeTestDatabaseError(
            f"{ENV_VAR}: database name {url.database!r} must match {_DB_NAME_RE.pattern}."
        )

    bad_keys = sorted(k for k in url.query if k.lower() not in _ALLOWED_QUERY_KEYS)
    if bad_keys:
        raise UnsafeTestDatabaseError(f"{ENV_VAR}: query parameters {bad_keys} could redirect the connection.")

    set_pg = sorted(v for v in _FORBIDDEN_ENV_VARS if env.get(v))
    if set_pg:
        raise UnsafeTestDatabaseError(
            f"Environment variables {set_pg} can override the connection target; unset them to run tests."
        )

    normalized = _normalize(url)
    other = (env.get("DATABASE_URL") or "").strip()
    if other:
        try:
            if _normalize(make_url(other.replace("postgres://", "postgresql://", 1))) == normalized:
                raise UnsafeTestDatabaseError(f"{ENV_VAR} must not be identical to DATABASE_URL.")
        except UnsafeTestDatabaseError:
            raise
        except Exception:  # noqa: BLE001 - unparsable DATABASE_URL cannot equal ours
            pass
    return normalized


def verify_live_target(connection, expected_url: str) -> None:
    """Second line of defence, run on a live connection before destructive SQL."""
    expected_db = make_url(expected_url).database
    actual_db = connection.exec_driver_sql("SELECT current_database()").scalar()
    if actual_db != expected_db or not _DB_NAME_RE.fullmatch(actual_db or ""):
        raise UnsafeTestDatabaseError(
            f"Connected database {actual_db!r} does not match the validated target {expected_db!r}."
        )
    marker = connection.exec_driver_sql(
        "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = current_database()"
    ).scalar()
    if marker != DISPOSABLE_MARKER:
        raise UnsafeTestDatabaseError(
            f"Database {actual_db!r} is not marked disposable. Run: "
            f"COMMENT ON DATABASE {actual_db} IS '{DISPOSABLE_MARKER}';"
        )
