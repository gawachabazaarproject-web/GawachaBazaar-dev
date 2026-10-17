"""Generate docs/04-database/DATABASE_SCHEMA.md from the SQLAlchemy models (Base.metadata).
Read-only; never connects to a database.

Run from backend/:
    venv/Scripts/python.exe -I ../docs/_tools/gen_schema_reference.py > ../docs/04-database/DATABASE_SCHEMA.md
"""

import os
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
os.environ["DATABASE_URL"] = "postgresql+psycopg://x:x@127.0.0.1:1/x"  # unroutable; never connects
sys.path.insert(0, str(BACKEND))

import app.models  # noqa: E402,F401  (registers every model on Base.metadata)
from app.db.base import Base  # noqa: E402

GROUPS = [
    ("Identity and access", ["users", "roles", "user_roles", "addresses", "wishlist_items", "customer_notes", "push_tokens"]),
    ("Catalog and content", ["categories", "products", "product_variants", "product_images", "prices", "ads", "home_slides"]),
    ("Supply, farms and packaging", ["suppliers", "supplier_products", "supplier_evaluations", "farms", "batches", "quality_checks",
                                     "packaging_operations", "packaging_inputs", "packaging_outputs"]),
    ("Inventory", ["inventory_locations", "inventory_lots", "stock_movements", "inventory_reservations", "inventory_reservation_items"]),
    ("Cart, checkout and orders", ["carts", "cart_items", "checkout_sessions", "orders", "order_items", "order_addresses"]),
    ("Payments and refunds", ["payments", "payment_transactions", "payment_webhook_events", "refunds"]),
    ("Fulfillment", ["fulfillments"]),
    ("Promotions", ["promotions", "promotion_targets", "promotion_eligible_customers", "promotion_redemptions"]),
    ("Bulk commerce", ["bulk_customer_profiles", "bulk_order_requests", "bulk_order_request_items", "quotes", "quote_versions", "quote_items"]),
    ("Audit", ["admin_action_logs"]),
]

tables = {t.name: t for t in Base.metadata.sorted_tables}
listed = {n for _, ns in GROUPS for n in ns}
missing = sorted(set(tables) - listed)
if missing:
    GROUPS.append(("Other (not grouped)", missing))
unknown = sorted(listed - set(tables))
if unknown:
    raise SystemExit(f"GROUPS names tables that no longer exist: {unknown}")


def default_of(c):
    if getattr(c, "identity", None) is not None:
        return "identity"
    sd = c.server_default
    if sd is None:
        return ""
    arg = getattr(sd, "arg", None)
    return str(arg) if arg is not None else "(server default)"


def esc(s):
    return str(s).replace("|", "\\|")


print("# Database Schema")
print()
print(
    f"> **Status:** Verified (generated from the ORM models). **Generated:** {date.today().isoformat()} by "
    "[`docs/_tools/gen_schema_reference.py`](../_tools/gen_schema_reference.py)."
)
print(
    "> **Evidence:** [`backend/app/models/`](../../backend/app/models) (SQLAlchemy 2 declarative models, "
    f"{len(tables)} tables) and the migration history in [`backend/alembic/versions/`](../../backend/alembic/versions). "
    "The models were compared with a database migrated to head using `alembic check` (see [MIGRATIONS.md](MIGRATIONS.md)). "
    "`alembic_version` is Alembic's own table and is not listed."
)
print()
print(
    "Relationships between tables: [ENTITY_RELATIONSHIPS.md](ENTITY_RELATIONSHIPS.md). Retention and lifecycle: "
    "[DATA_RETENTION.md](DATA_RETENTION.md). Business meaning of statuses: the domain documents in "
    "[`../05-domains/`](../05-domains)."
)
print()
print(
    "Timestamps show as `DATETIME` here (the ORM type) but are `timestamp with time zone` in PostgreSQL "
    "(checked on a migrated database for every `created_at`/`updated_at`/`placed_at`/`expires_at`/`starts_at`/`paid_at` "
    "column). Primary keys are `BIGINT` identity columns. Money columns are `NUMERIC(12,2)`, quantities "
    "`NUMERIC(12,3)`. `CHECK` constraints are enforced by PostgreSQL, so status vocabularies cannot drift from the "
    "database without a migration. Indexes marked *partial* carry a `WHERE` clause that this listing does not print; "
    "read the model for the predicate."
)
print()
print("## Table index")
print()
print("| Group | Tables |")
print("|---|---|")
for g, names in GROUPS:
    print(f"| {g} | " + ", ".join(f"[`{n}`](#{n})" for n in names) + " |")
print()

for g, names in GROUPS:
    print(f"## {g}")
    print()
    for n in names:
        t = tables[n]
        print(f"### {n}")
        print()
        print("| Column | Type | Null | Default | Key / reference |")
        print("|---|---|---|---|---|")
        for c in t.columns:
            keys = []
            if c.primary_key:
                keys.append("PK")
            for f in c.foreign_keys:
                od = f.ondelete
                keys.append(f"FK -> {f.column.table.name}.{f.column.name}" + (f" (ON DELETE {od})" if od else ""))
            print(
                f"| `{c.name}` | {esc(c.type)} | {'yes' if c.nullable else 'no'} | {esc(default_of(c))} | {'; '.join(keys)} |"
            )
        print()
        cons = []
        for k in t.constraints:
            kind = k.__class__.__name__
            if kind == "CheckConstraint":
                cons.append(f"- CHECK `{k.name}`: `{esc(k.sqltext)}`")
            elif kind == "UniqueConstraint":
                cons.append(f"- UNIQUE `{k.name or '(unnamed)'}`: ({', '.join(c.name for c in k.columns)})")
        for i in t.indexes:
            cons.append(f"- {'UNIQUE ' if i.unique else ''}INDEX `{i.name}`: ({', '.join(c.name for c in i.columns)})"
                        + (" - partial/filtered (see model)" if i.dialect_options.get("postgresql", {}).get("where") is not None else ""))
        if cons:
            # SQLAlchemy keeps constraints in a set, so sort for reproducible output.
            kind_order = {"- UNIQUE `": 0, "- CHECK `": 1, "- UNIQUE INDEX": 2, "- INDEX": 3}
            cons.sort(key=lambda s: (next((v for k, v in kind_order.items() if s.startswith(k)), 9), s))
            print("Constraints and indexes:")
            print()
            print("\n".join(cons))
            print()
