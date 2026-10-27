"""inventory canonical base units (phase 1: additive)

Revision ID: e5f6a7b80923
Revises: d3e4f5a60712
Create Date: 2026-10-27 18:00:00.000000

Adds EXACT integer base-unit columns (grams / ml / pieces / boxes) next to the
legacy 3-decimal pack columns and backfills them ONLY where the conversion is
mathematically exact. Anything that is not (e.g. 0.416 dozen = 4.992 pieces) is
NOT rounded: it is written to inventory_base_migration_report and the lot is
left quarantined (both base columns NULL) until a human resolves it.

The old pack columns are kept; a trigger derives them from the base columns (and
derives the base columns for legacy writers), so existing code keeps working.
The conversion factors below are a frozen snapshot of app/services/units.py at
the time of this revision (migrations must not import application code).
"""
import json
from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa

from alembic import op

revision: str = 'e5f6a7b80923'
down_revision: str | None = 'd3e4f5a60712'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FACTORS = {"KG": 1000, "G": 1, "L": 1000, "ML": 1, "UNIT": 1, "DOZEN": 12, "BOX": 1, "PACK": 1}
_FAMILY = {"KG": "MASS", "G": "MASS", "L": "VOLUME", "ML": "VOLUME", "UNIT": "COUNT", "DOZEN": "COUNT", "BOX": "BOX", "PACK": "PACK"}
_CASE = "CASE v.unit " + " ".join(f"WHEN '{u}' THEN {f}" for u, f in _FACTORS.items()) + " END"

_TRIGGER_FN = r"""
CREATE OR REPLACE FUNCTION gb_exact_base(packs numeric, sz bigint) RETURNS bigint AS $$
DECLARE v numeric;
BEGIN
  v := packs * sz;
  IF v <> trunc(v) THEN
    RAISE EXCEPTION 'quantity % of a size of % base units is not a whole number of base units', packs, sz
      USING ERRCODE = '22023';
  END IF;
  RETURN v::bigint;
END $$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION gb_sync_lot_base() RETURNS trigger AS $$
DECLARE sz bigint;
BEGIN
  SELECT size_base INTO sz FROM product_variants WHERE id = NEW.variant_id;
  IF TG_OP = 'INSERT' THEN
    IF NEW.quantity_base IS NULL AND NEW.reserved_base IS NULL THEN
      -- legacy writer (packs are the input): derive the exact base amounts
      NEW.quantity_base := gb_exact_base(NEW.quantity, sz);
      NEW.reserved_base := gb_exact_base(COALESCE(NEW.reserved_quantity, 0), sz);
    ELSE
      NEW.reserved_base := COALESCE(NEW.reserved_base, 0);
      NEW.quantity := round(NEW.quantity_base::numeric / sz, 3);
      NEW.reserved_quantity := round(NEW.reserved_base::numeric / sz, 3);
    END IF;
    RETURN NEW;
  END IF;

  IF NEW.quantity_base IS NULL THEN
    -- quarantined legacy lot: stays on legacy pack semantics until explicitly resolved
    RETURN NEW;
  END IF;
  IF OLD.quantity_base IS NULL THEN
    -- explicit resolution by an admin: the base amount is now authoritative
    NEW.reserved_base := COALESCE(NEW.reserved_base, 0);
    NEW.quantity := round(NEW.quantity_base::numeric / sz, 3);
    NEW.reserved_quantity := round(NEW.reserved_base::numeric / sz, 3);
    RETURN NEW;
  END IF;

  IF NEW.quantity_base IS DISTINCT FROM OLD.quantity_base THEN
    NEW.quantity := round(NEW.quantity_base::numeric / sz, 3);
  ELSIF NEW.quantity IS DISTINCT FROM OLD.quantity THEN
    NEW.quantity_base := gb_exact_base(NEW.quantity, sz);
  END IF;
  IF NEW.reserved_base IS DISTINCT FROM OLD.reserved_base THEN
    NEW.reserved_quantity := round(NEW.reserved_base::numeric / sz, 3);
  ELSIF NEW.reserved_quantity IS DISTINCT FROM OLD.reserved_quantity THEN
    NEW.reserved_base := gb_exact_base(NEW.reserved_quantity, sz);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    bind = op.get_bind()

    # ---- 1. variants: size_base (exact integer base units in one pack) ----
    op.add_column('product_variants', sa.Column('size_base', sa.BigInteger(), nullable=True))
    bad = bind.execute(sa.text(
        f"SELECT v.id, v.name, v.unit, v.quantity FROM product_variants v "
        f"WHERE v.quantity * ({_CASE}) <> trunc(v.quantity * ({_CASE})) ORDER BY v.id"
    )).fetchall()
    if bad:
        raise RuntimeError(
            "Refusing to migrate: these sizes are not a whole number of base units "
            "(g / ml / pieces), so inventory cannot be accounted exactly: "
            + "; ".join(f"variant {r[0]} {r[1]!r} = {r[3]} {r[2]}" for r in bad)
            + ". Change those sizes (e.g. 0.0005 kg -> 0.5 g is not allowed; use whole grams) and re-run."
        )
    op.execute(f"UPDATE product_variants v SET size_base = (v.quantity * ({_CASE}))::bigint")
    op.alter_column('product_variants', 'size_base', nullable=False)
    op.create_check_constraint('ck_product_variants_size_base', 'product_variants', 'size_base > 0')

    # ---- 2. lots, movements, reservation items: base columns ----
    op.add_column('inventory_lots', sa.Column('quantity_base', sa.BigInteger(), nullable=True))
    op.add_column('inventory_lots', sa.Column('reserved_base', sa.BigInteger(), nullable=True))
    op.add_column('stock_movements', sa.Column('quantity_base', sa.BigInteger(), nullable=True))
    op.add_column('inventory_reservation_items', sa.Column('quantity_base', sa.BigInteger(), nullable=True))

    # ---- 3. report table ----
    op.create_table(
        'inventory_base_migration_report',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('kind', sa.String(length=40), nullable=False),
        sa.Column('lot_id', sa.BigInteger(), nullable=True),
        sa.Column('product_id', sa.BigInteger(), nullable=True),
        sa.Column('variant_id', sa.BigInteger(), nullable=True),
        sa.Column('details', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # ---- 4. backfill lots: exact only ----
    op.execute(
        """
        UPDATE inventory_lots l SET
          quantity_base = (l.quantity * v.size_base)::bigint,
          reserved_base = (l.reserved_quantity * v.size_base)::bigint
        FROM product_variants v
        WHERE v.id = l.variant_id
          AND l.quantity * v.size_base = trunc(l.quantity * v.size_base)
          AND l.reserved_quantity * v.size_base = trunc(l.reserved_quantity * v.size_base)
        """
    )
    # items: exact only; movements: exact only (history, informational)
    op.execute(
        """
        UPDATE inventory_reservation_items i SET quantity_base = (i.quantity * v.size_base)::bigint
        FROM inventory_lots l JOIN product_variants v ON v.id = l.variant_id
        WHERE l.id = i.inventory_lot_id AND i.quantity * v.size_base = trunc(i.quantity * v.size_base)
        """
    )
    op.execute(
        """
        UPDATE stock_movements m SET quantity_base = (m.quantity * v.size_base)::bigint
        FROM inventory_lots l JOIN product_variants v ON v.id = l.variant_id
        WHERE l.id = m.inventory_lot_id AND m.quantity * v.size_base = trunc(m.quantity * v.size_base)
        """
    )
    # A lot that carries a LIVE reservation item we could not convert exactly cannot
    # have a trustworthy reserved_base: quarantine the whole lot as well.
    op.execute(
        """
        UPDATE inventory_lots SET quantity_base = NULL, reserved_base = NULL
        WHERE quantity_base IS NOT NULL AND id IN (
          SELECT i.inventory_lot_id FROM inventory_reservation_items i
          JOIN inventory_reservations r ON r.id = i.reservation_id
          WHERE i.quantity_base IS NULL AND r.status IN ('ACTIVE', 'COMMITTED'))
        """
    )

    # ---- 5. report every quarantined lot (nothing is modified or rounded) ----
    rows = bind.execute(sa.text(
        """
        SELECT l.id, l.quantity, l.reserved_quantity, v.id, v.name, v.unit, v.size_base, p.id, p.name,
               loc.name, b.id, b.batch_code, b.expiry_date
        FROM inventory_lots l
        JOIN product_variants v ON v.id = l.variant_id
        JOIN products p ON p.id = v.product_id
        JOIN inventory_locations loc ON loc.id = l.location_id
        JOIN batches b ON b.id = l.batch_id
        WHERE l.quantity_base IS NULL ORDER BY l.id
        """
    )).fetchall()
    for (lot_id, qty, rsv, vid, vname, unit, sz, pid, pname, wh, bid, bcode, expiry) in rows:
        calc = Decimal(qty) * sz
        nearest = int(calc.to_integral_value())
        details = {
            "lot_id": lot_id, "product": pname, "variant": vname, "unit": unit, "size_base": int(sz),
            "old_quantity_packs": str(qty), "old_reserved_packs": str(rsv),
            "calculated_base": str(calc), "nearest_representable_base": nearest,
            "difference_base": str(calc - nearest), "warehouse": wh, "batch_id": bid,
            "batch_code": bcode, "expiry_date": expiry.isoformat() if expiry else None,
            "action": "quarantined: excluded from sellable stock until resolved by an admin",
        }
        bind.execute(
            sa.text(
                "INSERT INTO inventory_base_migration_report (kind, lot_id, product_id, variant_id, details) "
                "VALUES ('LOT_NOT_EXACT', :lot, :pid, :vid, CAST(:d AS jsonb))"
            ),
            {"lot": lot_id, "pid": pid, "vid": vid, "d": json.dumps(details)},
        )

    # ---- 6. product reserve levels (base amount per product & family) ----
    op.create_table(
        'product_stock_reserves',
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column('family', sa.String(length=20), nullable=False),
        sa.Column('reserve_base', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('reserve_base >= 0', name='ck_product_stock_reserves_base'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('product_id', 'family', name='pk_product_stock_reserves'),
    )
    variants = bind.execute(sa.text(
        "SELECT v.product_id, v.id, v.name, v.unit, v.size_base, v.reserve_level FROM product_variants v "
        "WHERE v.status <> 'ARCHIVED' ORDER BY v.product_id, v.id"
    )).fetchall()
    groups: dict[tuple[int, str], list] = {}
    for pid, vid, vname, unit, sz, level in variants:
        groups.setdefault((pid, _FAMILY[unit]), []).append((vid, vname, unit, int(sz), level))
    for (pid, family), vs in groups.items():
        explicit = [v for v in vs if v[4] is not None]
        if not explicit:
            continue  # legacy default (10 packs of each size) keeps applying: nothing to convert
        bases = {Decimal(v[4]) * v[3] for v in explicit}
        clean = len(explicit) == len(vs) and len(bases) == 1 and all(b == b.to_integral_value() for b in bases)
        if clean:
            op.execute(
                sa.text(
                    "INSERT INTO product_stock_reserves (product_id, family, reserve_base) VALUES (:p, :f, :b)"
                ).bindparams(p=pid, f=family, b=int(next(iter(bases))))
            )
        else:
            details = {
                "product_id": pid, "family": family,
                "sizes": [{"variant_id": v[0], "name": v[1], "unit": v[2], "size_base": v[3],
                           "reserve_packs": None if v[4] is None else str(v[4]),
                           "reserve_base": None if v[4] is None else str(Decimal(v[4]) * v[3])} for v in vs],
                "action": "left on the legacy per-size rule; set a product-level reserve in Inventory when ready",
            }
            op.execute(
                sa.text(
                    "INSERT INTO inventory_base_migration_report (kind, product_id, details) "
                    "VALUES ('RESERVE_LEVEL_AMBIGUOUS', :p, CAST(:d AS jsonb))"
                ).bindparams(p=pid, d=json.dumps(details))
            )

    # ---- 7. constraints + compatibility trigger (after the backfill) ----
    op.create_check_constraint(
        'ck_inventory_lots_base', 'inventory_lots',
        '(quantity_base IS NULL AND reserved_base IS NULL) OR '
        '(quantity_base >= 0 AND reserved_base >= 0 AND reserved_base <= quantity_base)',
    )
    op.drop_constraint('ck_stock_movements_quantity', 'stock_movements', type_='check')
    op.create_check_constraint(
        'ck_stock_movements_quantity', 'stock_movements', 'quantity > 0 OR COALESCE(quantity_base, 0) > 0'
    )
    op.drop_constraint('ck_inventory_reservation_items_quantity', 'inventory_reservation_items', type_='check')
    op.create_check_constraint(
        'ck_inventory_reservation_items_quantity', 'inventory_reservation_items',
        'quantity > 0 OR COALESCE(quantity_base, 0) > 0'
    )
    op.execute(_TRIGGER_FN)
    op.execute(
        "CREATE TRIGGER trg_gb_sync_lot_base BEFORE INSERT OR UPDATE ON inventory_lots "
        "FOR EACH ROW EXECUTE FUNCTION gb_sync_lot_base()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_gb_sync_lot_base ON inventory_lots")
    op.execute("DROP FUNCTION IF EXISTS gb_sync_lot_base()")
    op.execute("DROP FUNCTION IF EXISTS gb_exact_base(numeric, bigint)")
    op.drop_constraint('ck_stock_movements_quantity', 'stock_movements', type_='check')
    op.create_check_constraint('ck_stock_movements_quantity', 'stock_movements', 'quantity > 0')
    op.drop_constraint('ck_inventory_reservation_items_quantity', 'inventory_reservation_items', type_='check')
    op.create_check_constraint('ck_inventory_reservation_items_quantity', 'inventory_reservation_items', 'quantity > 0')
    op.drop_constraint('ck_inventory_lots_base', 'inventory_lots', type_='check')
    op.drop_table('product_stock_reserves')
    op.drop_table('inventory_base_migration_report')
    op.drop_column('inventory_reservation_items', 'quantity_base')
    op.drop_column('stock_movements', 'quantity_base')
    op.drop_column('inventory_lots', 'reserved_base')
    op.drop_column('inventory_lots', 'quantity_base')
    op.drop_constraint('ck_product_variants_size_base', 'product_variants', type_='check')
    op.drop_column('product_variants', 'size_base')
