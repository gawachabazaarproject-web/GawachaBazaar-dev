"""Realistic API load test against scripts/loadtest_server.py (dev tool).

    # 1. disposable DB at alembic head, Redis, OSRM running; then
    python scripts/loadtest_api.py seed  --users 1000 --products 200
    python scripts/loadtest_api.py run   --vus 10 --seconds 120 --think 2,5 \\
           --server-pid <pid of loadtest_server> --redis redis://127.0.0.1:16379/0

`seed` fills the database (REFUSES a non-local / non-*_test database). `run`
simulates virtual users (browse 60%, cart+quote 25%, checkout 5%, history 10%),
with think time between steps, and prints per-endpoint p50/p95/p99, error rate,
server RSS/CPU (psutil), DB connections and Redis memory. Results describe THIS
host only.
"""

import argparse
import json
import random
import statistics
import threading
import time
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import psutil
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings

LAT, LNG = (21.05, 21.25), (78.98, 79.22)


def _engine():
    url = settings.DATABASE_URL
    if "127.0.0.1" not in url and "localhost" not in url:
        raise SystemExit("refusing: DATABASE_URL is not local")
    if not url.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
        raise SystemExit("refusing: database name must end with _test")
    return create_engine(url)


def seed(users: int, products: int) -> None:
    from app.core.roles import CUSTOMER, WHOLESALER
    from app.models.address import Address
    from app.models.batch import Batch
    from app.models.category import Category
    from app.models.inventory_location import InventoryLocation
    from app.models.inventory_lot import InventoryLot
    from app.models.price import Price
    from app.models.product import Product
    from app.models.product_variant import ProductVariant
    from app.models.role import Role
    from app.models.user import User
    from app.models.user_role import UserRole

    eng = _engine()
    rng = random.Random(7)
    with Session(eng) as db:
        db.execute(text("TRUNCATE TABLE users, roles, categories, inventory_locations RESTART IDENTITY CASCADE"))
        db.commit()
        roles = {n: Role(name=n, description=n) for n in (CUSTOMER, WHOLESALER)}
        db.add_all(roles.values())
        db.flush()
        ws = User(name="ws", email="ws@loadtest.example", phone="+910000000001", status="ACTIVE", firebase_uid="lt-ws")
        db.add(ws)
        db.flush()
        db.add(UserRole(user_id=ws.id, role_id=roles[WHOLESALER].id, is_primary=True))
        loc = InventoryLocation(
            name="LT Hub", code="LT-HUB", type="WAREHOUSE", address_line_1="x", city="Nagpur", state="MH",
            postal_code="440001", status="ACTIVE", latitude=Decimal("21.1497877"), longitude=Decimal("79.0806859"),
            is_packing_point=True,
        )
        db.add(loc)
        cats = [Category(name=f"Cat {i}", slug=f"cat-{i}", status="ACTIVE") for i in range(10)]
        db.add_all(cats)
        db.flush()
        now = datetime.now(UTC) - timedelta(days=1)
        for i in range(products):
            p = Product(category_id=cats[i % 10].id, name=f"Product {i}", slug=f"product-{i}", status="ACTIVE")
            db.add(p)
            db.flush()
            batch = Batch(wholesaler_user_id=ws.id, product_id=p.id, batch_code=f"B{i}", harvest_date=date(2026, 1, 1),
                          quantity=Decimal("1000000"), unit="KG", status="APPROVED")
            db.add(batch)
            db.flush()
            for j, name in enumerate(("500 G", "1 KG")):
                v = ProductVariant(product_id=p.id, name=name, sku=f"SKU-{i}-{j}", unit="KG",
                                   quantity=Decimal("0.500") if j == 0 else Decimal("1.000"), status="ACTIVE")
                db.add(v)
                db.flush()
                db.add(Price(variant_id=v.id, price=Decimal(rng.randint(20, 200)), currency="INR", valid_from=now, is_active=True))
                db.add(InventoryLot(batch_id=batch.id, variant_id=v.id, location_id=loc.id,
                                    quantity=Decimal("100000"), status="ACTIVE"))
        for n in range(1, users + 1):
            u = User(name=f"User {n}", email=f"lt-{n}@loadtest.example", phone=f"+9190{n:08d}", status="ACTIVE",
                     firebase_uid=f"lt-{n}")
            db.add(u)
            db.flush()
            db.add(UserRole(user_id=u.id, role_id=roles[CUSTOMER].id, is_primary=True))
            db.add(Address(user_id=u.id, label="Home", address_line_1="1 Test Rd", city="Nagpur", state="MH",
                           postal_code="440001", is_default=True,
                           latitude=Decimal(f"{rng.uniform(*LAT):.6f}"), longitude=Decimal(f"{rng.uniform(*LNG):.6f}")))
        db.commit()
    print(f"seeded {users} users, {products} products ({products * 2} variants)")


def pct(vals, p):
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(len(vals) * p))]


def run(args) -> None:
    base = args.base.rstrip("/") + "/api/v1"
    eng = _engine()
    with Session(eng) as db:
        n_users = db.execute(text("select count(*) from users where firebase_uid like 'lt-%'")).scalar() - 1
        prods = [r[0] for r in db.execute(text("select id from products order by id"))]
        variants = [r[0] for r in db.execute(text("select id from product_variants order by id"))]
        addr = {r[0]: r[1] for r in db.execute(text("select user_id, id from addresses"))}
        uid_of = {r[0]: r[1] for r in db.execute(text("select firebase_uid, id from users"))}
    lat = defaultdict(list)
    errs = defaultdict(int)
    lock = threading.Lock()
    stop = threading.Event()
    think_lo, think_hi = (float(x) for x in args.think.split(","))

    def call(client, name, method, path, **kw):
        t = time.perf_counter()
        try:
            r = client.request(method, base + path, **kw)
            ms = (time.perf_counter() - t) * 1000
            with lock:
                lat[name].append(ms)
                if r.status_code >= 400:
                    errs[f"{name} {r.status_code}"] += 1
            return r
        except Exception as exc:  # noqa: BLE001
            with lock:
                errs[f"{name} {type(exc).__name__}"] += 1
            return None

    def vu(seed):
        rng = random.Random(seed)
        uidx = rng.randint(1, n_users)
        headers = {"Authorization": f"Bearer lt-{uidx}-" + "x" * 800}
        aid = addr[uid_of[f"lt-{uidx}"]]
        with httpx.Client(timeout=30, headers=headers) as c:
            while not stop.is_set():
                x = rng.random()
                if x < 0.60:
                    call(c, "GET categories", "GET", "/catalog/categories")
                    call(c, "GET products", "GET", "/catalog/products", params={"page_size": 20})
                    call(c, "GET product", "GET", f"/catalog/products/{rng.choice(prods)}")
                elif x < 0.85:
                    call(c, "POST cart item", "POST", "/cart/items",
                         json={"variant_id": rng.choice(variants), "quantity": "1"})
                    call(c, "GET cart", "GET", "/cart")
                    call(c, "POST delivery quote", "POST", "/delivery/quote", json={"address_id": aid})
                    call(c, "GET bazaar quote", "GET", "/bazaar/delivery-quote", params={"address_id": aid})
                elif x < 0.90:
                    call(c, "POST cart item", "POST", "/cart/items",
                         json={"variant_id": rng.choice(variants), "quantity": "1"})
                    call(c, "POST checkout", "POST", "/cart/checkout", json={"address_id": aid})
                else:
                    call(c, "GET orders", "GET", "/orders")
                time.sleep(rng.uniform(think_lo, think_hi))

    samples = {"rss_mb": [], "cpu": [], "db_conns": [], "redis_mb": []}

    def sampler():
        proc = psutil.Process(args.server_pid) if args.server_pid else None
        if proc:
            proc.cpu_percent(None)
        r = None
        if args.redis:
            import redis

            r = redis.Redis.from_url(args.redis)
        while not stop.is_set():
            time.sleep(1)
            if proc:
                samples["rss_mb"].append(proc.memory_info().rss / 1048576)
                samples["cpu"].append(proc.cpu_percent(None))
            with eng.connect() as conn:
                samples["db_conns"].append(
                    conn.execute(text("select count(*) from pg_stat_activity where datname = current_database()")).scalar())
            if r is not None:
                samples["redis_mb"].append(r.info("memory")["used_memory"] / 1048576)

    threads = [threading.Thread(target=vu, args=(i,), daemon=True) for i in range(args.vus)]
    sthread = threading.Thread(target=sampler, daemon=True)
    started = time.monotonic()
    sthread.start()
    for t in threads:
        t.start()
    time.sleep(args.seconds)
    stop.set()
    for t in threads:
        t.join(timeout=60)
    elapsed = time.monotonic() - started
    total = sum(len(v) for v in lat.values())
    out = {
        "vus": args.vus, "seconds": round(elapsed), "requests": total, "rps": round(total / elapsed, 1),
        "errors": dict(errs), "error_rate_pct": round(100 * sum(errs.values()) / max(total, 1), 2),
        "endpoints": {
            k: {"n": len(v), "p50": round(statistics.median(v), 1), "p95": round(pct(v, .95), 1),
                "p99": round(pct(v, .99), 1), "max": round(max(v), 1)} for k, v in sorted(lat.items())},
    }
    for k, v in samples.items():
        if v:
            out[k] = {"max": round(max(v), 1), "avg": round(sum(v) / len(v), 1)}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed")
    s.add_argument("--users", type=int, default=1000)
    s.add_argument("--products", type=int, default=200)
    r = sub.add_parser("run")
    r.add_argument("--base", default="http://127.0.0.1:18000")
    r.add_argument("--vus", type=int, default=10)
    r.add_argument("--seconds", type=int, default=60)
    r.add_argument("--think", default="2,5")
    r.add_argument("--server-pid", type=int)
    r.add_argument("--redis")
    a = ap.parse_args()
    seed(a.users, a.products) if a.cmd == "seed" else run(a)
