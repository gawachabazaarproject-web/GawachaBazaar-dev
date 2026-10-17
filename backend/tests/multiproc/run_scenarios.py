"""Multi-replica experiments: two real uvicorn processes (started like
start.sh) sharing one disposable PostgreSQL database.

NOT collected by pytest. Run manually:

    TEST_DATABASE_URL=postgresql+psycopg://qa_test:***@127.0.0.1:15432/gb_multiproc_test \
        venv/Scripts/python.exe -m tests.multiproc.run_scenarios

The database must pass tests/_db_safety.py (loopback, *_test name, disposable
marker). It is DROPPED and re-created (schema `public`) several times.

Scenarios (each reports evidence, not a verdict):
  S1  concurrent `alembic upgrade head` from two processes (rolling deploy)
  S2  rate limit (5/min on /auth/legacy-migrate) enforced per replica
  S3  X-Forwarded-For spoofing vs the `--forwarded-allow-ips "*"` setting
  S4  WebSocket event published on replica B reaching a client on replica A
  S5  reservation-expiry sweep running on both replicas at once
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, text

from tests._db_safety import resolve_test_database_url, verify_live_target

URL = resolve_test_database_url(os.environ)
os.environ["DATABASE_URL"] = URL
os.environ["APP_ENV"] = "testing"
for _n in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET", "CLOUDINARY_CLOUD_NAME",
           "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET", "GOOGLE_MAPS_API_KEY", "FIREBASE_SERVICE_ACCOUNT_JSON"):
    os.environ[_n] = ""

import httpx  # noqa: E402
import websockets  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

BACKEND = Path(__file__).resolve().parents[2]
EVIDENCE = BACKEND.parent / "docs" / "testing" / "evidence" / "multireplica"
EVIDENCE.mkdir(parents=True, exist_ok=True)
PORTS = {"A": 18001, "B": 18002}
RESULTS: dict = {}
ENGINE = create_engine(URL)


def guarded_admin(sql: str) -> None:
    with ENGINE.connect() as c:
        verify_live_target(c, URL)
        c.rollback()
    with ENGINE.execution_options(isolation_level="AUTOCOMMIT").connect() as c:
        verify_live_target(c, URL)
        c.exec_driver_sql(sql)


def reset_schema() -> None:
    ENGINE.dispose()
    guarded_admin("DROP SCHEMA public CASCADE")
    guarded_admin("CREATE SCHEMA public")


_ALEMBIC_SEQ = [0]


def alembic(target: str) -> subprocess.Popen:
    """Child output goes to a file: a full pipe would block a child while it
    holds uncommitted DDL and stall its sibling (a harness-induced deadlock)."""
    env = {**os.environ, "DATABASE_URL": URL}
    _ALEMBIC_SEQ[0] += 1
    f = open(EVIDENCE / f"alembic_{_ALEMBIC_SEQ[0]:02d}.log", "w", encoding="utf-8")  # noqa: SIM115
    proc = subprocess.Popen([sys.executable, "-m", "alembic", "upgrade", target], cwd=BACKEND, env=env,
                            stdout=f, stderr=subprocess.STDOUT, text=True)
    proc.logfile = f.name  # type: ignore[attr-defined]
    return proc


def version() -> str | None:
    try:
        with ENGINE.connect() as c:
            return c.execute(text("select version_num from alembic_version")).scalar()
    except Exception:  # noqa: BLE001
        return None


def spawn(name: str) -> subprocess.Popen:
    log = open(EVIDENCE / f"replica_{name}.log", "w", encoding="utf-8")  # noqa: SIM115
    # FORWARDED_ALLOW_IPS=* is what start.sh sets via --forwarded-allow-ips "*" (passed by env here:
    # the Windows launcher glob-expands a literal * argument).
    env = {**{k: v for k, v in os.environ.items() if k != "DATABASE_URL"},
           "TEST_DATABASE_URL": URL, "MP_SWEEP_SECONDS": "2", "PYTHONUNBUFFERED": "1",
           "FORWARDED_ALLOW_IPS": "*"}
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "tests.multiproc.replica_app:app", "--host", "127.0.0.1",
         "--port", str(PORTS[name]), "--workers", "1", "--proxy-headers", "--no-access-log"], cwd=BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT)


def wait_up(port: int) -> None:
    for _ in range(80):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise RuntimeError(f"replica on {port} did not start")


def base(name: str) -> str:
    return f"http://127.0.0.1:{PORTS[name]}/api/v1"


# --------------------------------------------------------------------------
def s1_migration_race() -> dict:
    out = {"rounds": []}
    for kind in ("empty->head", "empty->head", "empty->head", "2-pending->head", "2-pending->head", "2-pending->head"):
        reset_schema()
        if kind == "2-pending->head":
            p = alembic("f5b8d2c4e047")  # state just before the last two revisions
            p.wait(timeout=300)
        procs = [alembic("head"), alembic("head")]
        res = []
        for p in procs:
            p.wait(timeout=300)
            o = Path(p.logfile).read_text(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            res.append({"rc": p.returncode, "error_lines": [ln for ln in o.splitlines()
                                                              if re.search(r"error|exception|already exists|deadlock|duplicate", ln, re.I)][:4]})
        out["rounds"].append({"kind": kind, "procs": res, "final_version": version()})
    return out


def seed_customer(tag: str):
    from tests.test_phase_13_cart_orders import _ready_customer

    with sessionmaker(bind=ENGINE)() as db:
        user, _h, variant, address = _ready_customer(db, tag)
        return {"uid": user.firebase_uid or f"fb-uid-{user.id}", "user_id": user.id,
                "variant_id": variant.id, "address_id": address.id}


def hdr(c: dict) -> dict:
    return {"Authorization": f"Bearer mp.{c['uid']}"}


def place_pending_order(replica: str, c: dict) -> int:
    r = httpx.post(f"{base(replica)}/cart/items", json={"variant_id": c["variant_id"], "quantity": "1"}, headers=hdr(c))
    assert r.status_code in (200, 201), r.text
    r = httpx.post(f"{base(replica)}/cart/checkout", json={"address_id": c["address_id"]}, headers=hdr(c))
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def s2_s3_rate_limit() -> dict:
    payload = {"identifier": "nobody@example.com", "password": "x"}

    def burst(replica, n, xff=None):
        codes = []
        for i in range(n):
            h = {"X-Forwarded-For": xff(i)} if xff else {}
            codes.append(httpx.post(f"{base(replica)}/auth/legacy-migrate", json=payload, headers=h).status_code)
        return codes

    out = {}
    a = burst("A", 8)
    b = burst("B", 8)
    out["S2_same_client_8_requests_to_A"] = a
    out["S2_same_client_8_requests_to_B"] = b
    out["S2_allowed_total_across_replicas"] = sum(1 for x in a + b if x != 429)
    out["S2_documented_limit_per_minute"] = 5
    same = burst("A", 8, xff=lambda i: "198.51.100.7, 203.0.113.9")
    out["S3_control_same_xff_x8"] = same
    spoof = burst("A", 12, xff=lambda i: f"10.9.{i}.1, 203.0.113.9")  # varying leftmost, fixed 'real' client at right
    out["S3_varying_leftmost_xff_x12"] = spoof
    out["S3_requests_rate_limited_with_spoof"] = sum(1 for x in spoof if x == 429)
    return out


async def _ws_listen(replica: str, token: str, seconds: float) -> list:
    got = []
    try:
        async with websockets.connect(f"ws://127.0.0.1:{PORTS[replica]}/api/v1/ws/events?token={token}") as ws:
            end = time.time() + seconds
            while time.time() < end:
                try:
                    got.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5)))
                except TimeoutError:
                    pass
    except Exception as exc:  # noqa: BLE001
        got.append({"ws_error": repr(exc)[:120]})
    return got


async def _s4(c: dict, o_same: int, o_cross: int) -> dict:
    token = f"mp.{c['uid']}"
    listener = asyncio.create_task(_ws_listen("A", token, 6))
    await asyncio.sleep(1.5)
    await asyncio.to_thread(httpx.post, f"{base('A')}/orders/{o_same}/cancel", json={}, headers=hdr(c))
    await asyncio.sleep(1.0)
    await asyncio.to_thread(httpx.post, f"{base('B')}/orders/{o_cross}/cancel", json={}, headers=hdr(c))
    events = await listener
    return {"events_received_on_A": [e for e in events if "order_id" in e], "ws_errors": [e for e in events if "ws_error" in e]}


def s4_websocket() -> dict:
    c = seed_customer("ws")
    o_same, o_cross = place_pending_order("A", c), place_pending_order("A", c)
    res = asyncio.run(_s4(c, o_same, o_cross))
    res["order_cancelled_via_A (same replica as socket)"] = o_same
    res["order_cancelled_via_B (other replica)"] = o_cross
    ids = {e["order_id"] for e in res["events_received_on_A"]}
    res["socket_on_A_saw_event_for_A_action"] = o_same in ids
    res["socket_on_A_saw_event_for_B_action"] = o_cross in ids
    with ENGINE.connect() as db:
        res["both_orders_cancelled_in_db"] = [r[0] for r in db.execute(
            text("select status from orders where id in (:a,:b) order by id"), {"a": o_same, "b": o_cross})]
    return res


def pg_deadlocks() -> int:
    with ENGINE.connect() as c:
        return c.execute(text("select deadlocks from pg_stat_database where datname = current_database()")).scalar()


def s5_sweep() -> dict:
    c = seed_customer("sweep")
    n = 12
    ids = [place_pending_order("A" if i % 2 == 0 else "B", c) for i in range(n)]
    dl0 = pg_deadlocks()
    with ENGINE.begin() as db:
        db.execute(text("update inventory_reservations set expires_at = now() - interval '1 minute' where status='ACTIVE'"))
    time.sleep(10)
    with ENGINE.connect() as db:
        states = dict(db.execute(text("select status, count(*) from inventory_reservations group by 1")).all())
        lots = db.execute(text("select min(reserved_quantity), max(reserved_quantity), min(quantity - reserved_quantity) from inventory_lots")).one()
        ostates = dict(db.execute(text("select status, count(*) from orders group by 1")).all())
        mov = dict(db.execute(text("select movement_type, count(*) from stock_movements group by 1")).all())
    per_replica = {}
    for r in "AB":
        txt = (EVIDENCE / f"replica_{r}.log").read_text(encoding="utf-8", errors="replace")
        per_replica[r] = sum(int(m) for m in re.findall(r"INVENTORY_RESERVATION_SWEEP: expired_count=(\d+)", txt))
        per_replica[f"{r}_sweep_failures"] = len(re.findall(r"INVENTORY_RESERVATION_SWEEP_FAILED", txt))
    return {"reservations_created": n, "reservation_states": states, "order_states": ostates,
            "lot_reserved_min_max_free_min": [str(x) for x in lots], "stock_movements": mov,
            "sweep_reported_expired_by_replica": per_replica,
            "sum_reported_vs_actual": [per_replica["A"] + per_replica["B"], n],
            "pg_deadlocks_during_sweep": pg_deadlocks() - dl0}


def main() -> None:
    if os.environ.get("MP_SKIP_S1"):
        RESULTS.update(json.loads((EVIDENCE / "results.json").read_text(encoding="utf-8")))
    else:
        RESULTS["S1_migration_race"] = s1_migration_race()
    (EVIDENCE / "results.json").write_text(json.dumps(RESULTS, indent=2, default=str), encoding="utf-8")
    reset_schema()
    alembic("head").wait(timeout=300)
    procs = [spawn("A"), spawn("B")]
    try:
        for n in "AB":
            wait_up(PORTS[n])
        for name, fn in (("S2_S3_rate_limit_and_xff", s2_s3_rate_limit), ("S4_websocket_cross_replica", s4_websocket),
                         ("S5_reservation_sweep", s5_sweep)):
            if os.environ.get("MP_ONLY") and not name.startswith(os.environ["MP_ONLY"]):
                continue
            try:
                RESULTS[name] = fn()
            except Exception as exc:  # noqa: BLE001
                RESULTS[name] = {"harness_error": repr(exc)[:300]}
            (EVIDENCE / "results.json").write_text(json.dumps(RESULTS, indent=2, default=str), encoding="utf-8")
    finally:
        for p in procs:
            p.terminate()
    (EVIDENCE / "results.json").write_text(json.dumps(RESULTS, indent=2, default=str), encoding="utf-8")
    print(json.dumps(RESULTS, indent=2, default=str))


if __name__ == "__main__":
    main()
