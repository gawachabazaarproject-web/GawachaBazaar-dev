"""Exploratory capacity test: ONE backend process (started like start.sh) on a
disposable local DB, driven by 10 / 25 / 50 / 100 virtual users.

NOT a statement of production requirements - the load model is an assumption
(think time 0.2-0.6 s, the mix below) and generator, server and database all
share one developer machine. Stops escalating if error rate > 5 %, p99 > 8 s
or an integrity check fails.

    TEST_DATABASE_URL=postgresql+psycopg://qa_test:***@127.0.0.1:15432/gb_multiproc_test \
        venv/Scripts/python.exe -m tests.multiproc.perf

Per-iteration mix (authenticated customer, own basket):
  GET /catalog/products (list) . GET /catalog/products?q= (search) . GET product detail
  GET /home-slides . GET /offers . GET /auth/me . POST /cart/items . GET /cart
  every 8th iteration: POST /cart/checkout (Cash on Delivery order, real stock reservation)
  GET /orders
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
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
from sqlalchemy.orm import sessionmaker  # noqa: E402

BACKEND = Path(__file__).resolve().parents[2]
EVIDENCE = BACKEND.parent / "docs" / "testing" / "evidence" / "performance"
EVIDENCE.mkdir(parents=True, exist_ok=True)
PORT = 18010
BASE = f"http://127.0.0.1:{PORT}/api/v1"
ENGINE = create_engine(URL)
LEVELS = [int(x) for x in os.environ.get("PERF_LEVELS", "10,25,50,100").split(",")]
DURATION = int(os.environ.get("PERF_SECONDS", "45"))
N_CUSTOMERS = 100


def guarded(sql: str) -> None:
    with ENGINE.execution_options(isolation_level="AUTOCOMMIT").connect() as c:
        verify_live_target(c, URL)
        c.exec_driver_sql(sql)


def seed() -> list[dict]:
    from tests.test_phase_13_cart_orders import _ready_customer

    out = []
    with sessionmaker(bind=ENGINE)() as db:
        for i in range(N_CUSTOMERS):
            user, _h, variant, address = _ready_customer(db, f"perf{i}")
            out.append({"uid": user.firebase_uid or f"fb-uid-{user.id}", "variant_id": variant.id,
                        "address_id": address.id, "product_id": variant.product_id})
    return out


def spawn() -> subprocess.Popen:
    log = open(EVIDENCE / "server.log", "w", encoding="utf-8")  # noqa: SIM115
    env = {**{k: v for k, v in os.environ.items() if k != "DATABASE_URL"}, "TEST_DATABASE_URL": URL,
           "MP_SWEEP_SECONDS": "120", "PYTHONUNBUFFERED": "1", "FORWARDED_ALLOW_IPS": "*",
           "DEBUG": "false"}  # DEBUG=true turns on SQLAlchemy echo (db/session.py) and wrecks timings
    return subprocess.Popen([sys.executable, "-m", "uvicorn", "tests.multiproc.replica_app:app", "--host", "127.0.0.1",
                             "--port", str(PORT), "--workers", "1", "--proxy-headers", "--no-access-log"],
                            cwd=BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT)


def proc_sample(pid: int) -> tuple[float, float]:
    """(cumulative CPU seconds, working set MB) summed over the process and its
    children (the venv launcher stub is the parent of the real uvicorn worker)."""
    ps = (f"$all=@({pid})+@((Get-CimInstance Win32_Process -Filter 'ParentProcessId={pid}').ProcessId); "
          "$c=0;$m=0; foreach($i in $all){$p=Get-Process -Id $i -ErrorAction SilentlyContinue; "
          "if($p){$c+=$p.CPU;$m+=$p.WorkingSet64}}; \"$c $([math]::Round($m/1MB,1))\"")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30).stdout.split()
    return float(out[0]), float(out[1])


def db_conns() -> int:
    with ENGINE.connect() as c:
        return c.execute(text("select count(*) from pg_stat_activity where datname=current_database() "
                              "and pid<>pg_backend_pid()")).scalar()


def ms(seconds: float):
    """Seconds -> whole milliseconds; None when there were no samples (NaN)."""
    return None if seconds != seconds else round(seconds * 1000)


def pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


class Stats:
    def __init__(self) -> None:
        self.lat: dict[str, list[tuple[float, float]]] = defaultdict(list)  # (abs start, seconds)
        self.codes: Counter = Counter()
        self.errors: Counter = Counter()
        self.checkouts_ok = 0


async def vu(idx: int, cust: dict, products: list[int], stop_at: float, st: Stats, start_delay: float) -> None:
    headers = {"Authorization": f"Bearer mp.{cust['uid']}"}
    rng = random.Random(idx)
    async with httpx.AsyncClient(base_url=BASE, timeout=30, limits=httpx.Limits(max_connections=4)) as cl:

        async def call(name, method, url, **kw):
            t_abs, t0 = time.time(), time.perf_counter()
            try:
                r = await cl.request(method, url, **kw)
                code = r.status_code
            except Exception as exc:  # noqa: BLE001
                st.errors[type(exc).__name__] += 1
                st.codes[("EXC", t_abs)] += 1
                st.lat[name].append((t_abs, time.perf_counter() - t0))
                return None
            st.lat[name].append((t_abs, time.perf_counter() - t0))
            st.codes[(code, t_abs)] += 1
            return r

        await asyncio.sleep(start_delay)
        n = 0
        while time.time() < stop_at:
            n += 1
            await call("GET catalog list", "GET", "/catalog/products", params={"page": 1, "page_size": 20})
            await call("GET catalog search", "GET", "/catalog/products", params={"q": "perf", "page_size": 10})
            await call("GET product detail", "GET", f"/catalog/products/{rng.choice(products)}")
            await call("GET home-slides", "GET", "/home-slides")
            await call("GET offers", "GET", "/offers")
            await call("GET auth/me", "GET", "/auth/me", headers=headers)
            await call("POST cart/items", "POST", "/cart/items", headers=headers,
                       json={"variant_id": cust["variant_id"], "quantity": "1"})
            await call("GET cart", "GET", "/cart", headers=headers)
            if n % 8 == 0:
                r = await call("POST checkout (COD)", "POST", "/cart/checkout", headers=headers,
                               json={"address_id": cust["address_id"]})
                if r is not None and r.status_code in (200, 201):
                    st.checkouts_ok += 1
            await call("GET orders", "GET", "/orders", headers=headers)
            await asyncio.sleep(rng.uniform(0.2, 0.6))


def integrity(expected_orders: int) -> dict:
    with ENGINE.connect() as c:
        orders = c.execute(text("select count(*) from orders")).scalar()
        dup = c.execute(text("select count(*) from (select order_number from orders group by 1 having count(*)>1) x")).scalar()
        bad_lots = c.execute(text("select count(*) from inventory_lots where reserved_quantity < 0 or reserved_quantity > quantity")).scalar()
        resv = c.execute(text("select count(*) from inventory_reservations")).scalar()
        orphan = c.execute(text("select count(*) from orders o left join inventory_reservations r on r.order_id=o.id where r.id is null")).scalar()
        items = c.execute(text("select coalesce(sum(oi.quantity),0) from order_items oi join orders o on o.id=oi.order_id where o.status in ('PENDING','CONFIRMED')")).scalar()
        reserved = c.execute(text("select coalesce(sum(reserved_quantity),0) from inventory_lots")).scalar()
    ok = (orders == expected_orders and dup == 0 and bad_lots == 0 and orphan == 0 and reserved == items)
    return {"ok": ok, "orders_in_db": orders, "orders_expected": expected_orders, "duplicate_order_numbers": dup,
            "lots_out_of_bounds": bad_lots, "orders_without_reservation": orphan,
            "reserved_total": str(reserved), "ordered_units_open_orders": str(items)}


RAMP = int(os.environ.get("PERF_RAMP", "10"))


async def run_level(n: int, custs: list[dict], products: list[int], pid: int) -> dict:
    """VUs start staggered over RAMP seconds; statistics use only requests that
    STARTED after the ramp, so a synchronized thundering herd at t=0 (all users
    hitting the heaviest endpoint at once) does not masquerade as steady state."""
    st = Stats()
    t0 = time.time()
    window_start = t0 + RAMP
    stop_at = window_start + DURATION
    samples = {"db_conns": [], "rss_mb": []}
    cpu_at: dict[str, float] = {}

    async def sampler():
        while time.time() < stop_at:
            await asyncio.sleep(3)
            try:
                cpu, rss = await asyncio.to_thread(proc_sample, pid)
                if time.time() >= window_start:
                    cpu_at.setdefault("start", cpu)
                    cpu_at["start_t"] = cpu_at.get("start_t", time.time())
                    cpu_at["end"], cpu_at["end_t"] = cpu, time.time()
                    samples["rss_mb"].append(rss)
                    samples["db_conns"].append(await asyncio.to_thread(db_conns))
            except Exception:  # noqa: BLE001
                pass

    await asyncio.gather(sampler(), *(vu(i, custs[i % len(custs)], products, stop_at, st, i * RAMP / n) for i in range(n)))

    def in_window(pairs):
        return [d for t, d in pairs if t >= window_start]

    codes: Counter = Counter()
    for (code, t), c in st.codes.items():
        if t >= window_start:
            codes[code] += c
    total = sum(codes.values())
    all_lat = [d for v in st.lat.values() for d in in_window(v)]
    bad = sum(c for k, c in codes.items() if k == "EXC" or (isinstance(k, int) and k >= 500))
    client_err = sum(c for k, c in codes.items() if isinstance(k, int) and 400 <= k < 500)
    per = {k: {"n": len(in_window(v)), "p50_ms": ms(pct(in_window(v), 50)),
               "p95_ms": ms(pct(in_window(v), 95)), "p99_ms": ms(pct(in_window(v), 99))}
           for k, v in sorted(st.lat.items())}
    span = max(cpu_at.get("end_t", 0) - cpu_at.get("start_t", 0), 1e-9)
    cpu_cores = (cpu_at.get("end", 0) - cpu_at.get("start", 0)) / span
    return {"vus": n, "ramp_s": RAMP, "window_s": DURATION, "requests": total, "rps": round(total / DURATION, 1),
            "server_errors_5xx_or_exc": bad, "error_rate_pct": round(100 * bad / max(total, 1), 2),
            "http_4xx": client_err, "status_codes": {str(k): v for k, v in codes.items()},
            "exceptions": dict(st.errors),
            "overall_ms": {"p50": ms(pct(all_lat, 50)), "p95": ms(pct(all_lat, 95)),
                           "p99": ms(pct(all_lat, 99)), "mean": round(statistics.mean(all_lat) * 1000) if all_lat else None},
            "server_cpu_cores_avg": round(cpu_cores, 2),
            "server_rss_mb_max": max(samples["rss_mb"] or [0]), "db_connections_max": max(samples["db_conns"] or [0]),
            "per_endpoint": per, "checkouts_ok": st.checkouts_ok}


async def service_times(custs, products) -> dict:
    """Single user, no think time: the per-request cost with no queueing."""
    out: dict = {}
    h = {"Authorization": f"Bearer mp.{custs[0]['uid']}"}
    plan = [("GET catalog list", "GET", "/catalog/products", {"params": {"page": 1, "page_size": 20}}),
            ("GET catalog search", "GET", "/catalog/products", {"params": {"q": "perf", "page_size": 10}}),
            ("GET product detail", "GET", f"/catalog/products/{products[0]}", {}),
            ("GET home-slides", "GET", "/home-slides", {}), ("GET offers", "GET", "/offers", {}),
            ("GET auth/me", "GET", "/auth/me", {"headers": h}), ("GET cart", "GET", "/cart", {"headers": h}),
            ("GET orders", "GET", "/orders", {"headers": h})]
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as cl:
        for name, m, url, kw in plan:
            v = []
            for _ in range(30):
                t0 = time.perf_counter()
                await cl.request(m, url, **kw)
                v.append(time.perf_counter() - t0)
            out[name] = {"p50_ms": round(pct(v, 50) * 1000), "p95_ms": round(pct(v, 95) * 1000)}
    return out


async def probe(n: int, custs) -> dict:
    lat = []
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as cl:
        for _ in range(n):
            t0 = time.perf_counter()
            r = await cl.get("/auth/me", headers={"Authorization": f"Bearer mp.{custs[0]['uid']}"})
            lat.append((time.perf_counter() - t0, r.status_code))
            await asyncio.sleep(0.05)
    v = [x for x, _ in lat]
    return {"n": n, "p50_ms": round(pct(v, 50) * 1000), "p95_ms": round(pct(v, 95) * 1000),
            "non200": sum(1 for _, c in lat if c != 200)}


async def recovery_time(custs, cap_s: int = 600) -> dict:
    """After the load stops: seconds until 3 consecutive /auth/me answers are 200 and < 500 ms."""
    t0 = time.time()
    ok_streak, attempts = 0, 0
    h = {"Authorization": f"Bearer mp.{custs[0]['uid']}"}
    async with httpx.AsyncClient(base_url=BASE, timeout=5) as cl:
        while time.time() - t0 < cap_s:
            attempts += 1
            t1 = time.perf_counter()
            try:
                r = await cl.get("/auth/me", headers=h)
                good = r.status_code == 200 and (time.perf_counter() - t1) < 0.5
            except Exception:  # noqa: BLE001
                good = False
            ok_streak = ok_streak + 1 if good else 0
            if ok_streak >= 3:
                return {"recovered": True, "seconds_after_load_stopped": round(time.time() - t0, 1), "attempts": attempts}
            await asyncio.sleep(2)
    return {"recovered": False, "waited_seconds": cap_s, "attempts": attempts}


def main() -> None:
    import logging

    logging.disable(logging.CRITICAL)  # generator process only: the app logging config enables DEBUG for httpx
    guarded("DROP SCHEMA public CASCADE")
    guarded("CREATE SCHEMA public")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True,
                   env={**os.environ, "DATABASE_URL": URL}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    custs = seed()
    products = sorted({c["product_id"] for c in custs})
    server = spawn()
    results: dict = {"config": {"levels": LEVELS, "window_seconds_per_level": DURATION, "ramp_seconds": RAMP, "customers": N_CUSTOMERS,
                                "think_time_s": [0.2, 0.6], "checkout_every_n_iterations": 8,
                                "uvicorn_workers": 1, "debug": False, "db_pool": "pool_size=5,max_overflow=10 (app default)",
                                "note": "generator, server and Postgres share one 12-thread dev machine"},
                     "levels": []}
    try:
        for _ in range(80):
            try:
                if httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=1).status_code == 200:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        pid = server.pid
        results["baseline_1vu_probe"] = asyncio.run(probe(40, custs))
        results["single_user_service_times"] = asyncio.run(service_times(custs, products))
        total_checkouts = 0
        for n in LEVELS:
            lvl = asyncio.run(run_level(n, custs, products, pid))
            total_checkouts += lvl["checkouts_ok"]
            lvl["integrity"] = integrity(total_checkouts)
            results["levels"].append(lvl)
            (EVIDENCE / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
            print(f"[{n:>3} VU] rps={lvl['rps']} p50={lvl['overall_ms']['p50']}ms p95={lvl['overall_ms']['p95']}ms "
                  f"p99={lvl['overall_ms']['p99']}ms err={lvl['error_rate_pct']}% cpu={lvl['server_cpu_cores_avg']} "
                  f"rss={lvl['server_rss_mb_max']}MB dbconn={lvl['db_connections_max']} integrity={lvl['integrity']['ok']}", flush=True)
            if lvl["error_rate_pct"] > 5 or (lvl["overall_ms"]["p99"] or 0) > 8000 or lvl["overall_ms"]["p99"] is None or not lvl["integrity"]["ok"]:
                results["stopped_early"] = f"stop rule hit at {n} VUs"
                print("STOP RULE HIT:", results["stopped_early"], flush=True)
                break
            time.sleep(5)
        results["recovery_after_load"] = asyncio.run(recovery_time(custs))
        print("RECOVERY:", results["recovery_after_load"], flush=True)
    finally:
        server.terminate()
        (EVIDENCE / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps({"baseline": results["baseline_1vu_probe"], "recovery": results.get("recovery_after_load")}))


if __name__ == "__main__":
    main()
