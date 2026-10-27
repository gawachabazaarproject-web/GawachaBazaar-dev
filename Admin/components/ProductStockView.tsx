"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  expiryPhrase,
  fetchProductStock,
  fetchProductStockCard,
  InventoryApiError,
  packCount,
  packSize,
  plain,
  ProductStockItem,
  ProductStockListResponse,
  ProductStockOperation,
  setStockShares,
  StockFilter,
  stockErrorMessage,
} from "@/lib/inventory";
import { useWarehouses } from "@/lib/use-warehouses";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Pagination } from "@/components/Pagination";
import { TableSkeleton } from "@/components/TableSkeleton";
import { AddStockDialog, CorrectStockDialog, MoveStockDialog, RemoveStockAmountDialog } from "@/components/StockDialogs";
import type { StockNotice } from "@/components/StockActionBanner";
import { UNITS } from "@/lib/units";

const PAGE_SIZE = 20;
const num = (v: string | number) => String(Number(Number(v).toFixed(3)));

// pack unit -> [unit family, size of one unit in the family's base unit]
const FAMILY: Record<string, [string, number]> = Object.fromEntries(
  Object.entries(UNITS).map(([k, u]) => [k, [u.dimension, u.factor]]),
);
// What an assigned share is typed in, per family: [label, API unit, base units per typed unit].
const TYPED: Record<string, [string, string, number]> = {
  MASS: ["kg", "KG", UNITS.KG.factor], VOLUME: ["L", "L", UNITS.L.factor], COUNT: ["pieces", "UNIT", UNITS.UNIT.factor],
};

const EMPTY_TEXT: Record<StockFilter, { title: string; message: string }> = {
  all: { title: "No products found", message: "Try a different search or category." },
  low: { title: "Nothing is running low", message: "Every product is comfortably stocked." },
  out: { title: "Nothing is out of stock", message: "Every product has stock to sell." },
  expiring: { title: "Nothing is about to expire", message: "No stock expires in the next week." },
};

/**
 * Inventory by product: "What do we have?" One card per product with the
 * available amount in kg, what is promised to orders, where it is, and the
 * everyday actions. Lots, batches and sharing between sizes stay one click
 * away ("Sizes & sharing", "Stock details") for people who need them.
 */
export function ProductStockView({
  q,
  categoryId,
  filter,
  reloadKey,
  onNotice,
  onChanged,
}: {
  q: string;
  categoryId: string;
  filter: StockFilter;
  reloadKey: number;
  onNotice: (notice: StockNotice) => void;
  /** Something changed: the page refreshes its counts. */
  onChanged: () => void;
}) {
  const { getAccessToken } = useAuth();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ProductStockListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadedOnce = useRef(false);

  useEffect(() => setPage(1), [q, categoryId, filter]);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setError(null);
    try {
      setData(
        await fetchProductStock(token, {
          page,
          page_size: PAGE_SIZE,
          q: q || undefined,
          category_id: categoryId ? Number(categoryId) : undefined,
          status: filter === "all" ? undefined : filter,
        }),
      );
    } catch (err) {
      setError(stockErrorMessage(err, "load the stock", ""));
    } finally {
      setLoading(false);
      loadedOnce.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, q, categoryId, filter, reloadKey]);

  useEffect(() => {
    load();
  }, [load]);

  // Coming back to this tab after a while: show today's numbers, not the ones from this morning.
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible" && loadedOnce.current) {
        load();
        onChanged();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  if (loading && !loadedOnce.current) return <div className="rounded border border-neutral-200 bg-white"><TableSkeleton rows={6} columns={3} /></div>;
  if (error) return <div className="rounded border border-neutral-200 bg-white"><ErrorState message={error} onRetry={load} /></div>;
  if (!data || data.items.length === 0) {
    return (
      <div className="rounded border border-neutral-200 bg-white">
        <EmptyState icon="box" title={EMPTY_TEXT[filter].title} message={EMPTY_TEXT[filter].message} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {data.items.map((p) => (
        <ProductCard key={p.product_id} product={p} onNotice={onNotice} onChanged={() => { load(); onChanged(); }} />
      ))}
      <div className="rounded border border-neutral-200 bg-white">
        <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
      </div>
    </div>
  );
}

const STATUS_CHIP: Record<string, { text: string; cls: string }> = {
  LOW: { text: "Low stock", cls: "bg-status-warningLight text-status-warning" },
  OUT: { text: "Out of stock", cls: "bg-status-dangerLight text-status-danger" },
};

function ProductCard({
  product: p,
  onNotice,
  onChanged,
}: {
  product: ProductStockItem;
  onNotice: (notice: StockNotice) => void;
  onChanged: () => void;
}) {
  const { user } = useAuth();
  const { locations } = useWarehouses();
  const can = (perm: Parameters<typeof hasPermission>[1]) => !!(user && hasPermission(user.roles, perm));
  const canOpenProduct = can("products.read");
  const canReceive = can("inventory.receive");
  const canAdjust = can("inventory.adjust");
  const canReconcile = can("inventory.reconcile");
  const canTransfer = can("inventory.transfer");
  const hasStock = p.warehouses.length > 0;
  const canMove = canTransfer && locations.length > 1 && hasStock;

  const { getAccessToken } = useAuth();
  const [dialog, setDialog] = useState<"add" | "correct" | "remove" | "move" | null>(null);
  const [fresh, setFresh] = useState<ProductStockItem | null>(null);
  const [openError, setOpenError] = useState<string | null>(null);
  const [removeReason, setRemoveReason] = useState<string | undefined>(undefined);

  // Stock changes all day (customers, other staff). Read the latest numbers right
  // before a dialog opens so nobody corrects, removes or moves from a stale card.
  const openDialog = async (kind: "add" | "correct" | "remove" | "move", reason?: string) => {
    const token = getAccessToken();
    if (!token) return;
    setOpenError(null);
    try {
      setFresh(await fetchProductStockCard(token, p.product_id));
      setRemoveReason(reason);
      setDialog(kind);
    } catch (err) {
      setOpenError(stockErrorMessage(err, "load the latest stock", "Nothing was changed."));
    }
  };
  const [menuOpen, setMenuOpen] = useState(false);
  const [sizesOpen, setSizesOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menuOpen]);

  const done = (op: ProductStockOperation) => {
    onNotice({ message: op.message, operation: op.operation_id ? op : undefined });
    onChanged();
  };

  const live = p.product_status === "ACTIVE";
  const chip = live ? STATUS_CHIP[p.stock_status] : { text: p.product_status === "DRAFT" ? "Draft" : "Hidden", cls: "bg-neutral-100 text-neutral-600" };
  const expiring = p.expiry && p.expiry.days_left <= 7 ? p.expiry : null;
  const history = `/inventory?view=lot&q=${encodeURIComponent(p.product_name)}`;
  const available = p.totals.length === 0 ? "0 kg" : p.totals.map((t) => `${num(t.amount)} ${t.amount_unit}`).join(" + ");
  const reserved = p.totals.filter((t) => Number(t.reserved_amount) > 0);
  const menuItems: { label: string; onClick: () => void }[] = [
    ...(canReconcile && hasStock ? [{ label: "Correct stock count", onClick: () => openDialog("correct") }] : []),
    ...(canAdjust && hasStock ? [{ label: "Remove stock", onClick: () => openDialog("remove") }] : []),
    ...(canMove ? [{ label: "Move stock", onClick: () => openDialog("move") }] : []),
    { label: sizesOpen ? "Hide sizes & sharing" : "Sizes & sharing", onClick: () => setSizesOpen((v) => !v) },
  ];

  return (
    <div className="rounded border border-neutral-200 bg-white">
      <div className="flex flex-wrap items-start justify-between gap-4 px-4 py-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {canOpenProduct ? (
              <Link href={`/products/${p.product_id}`} className="font-medium text-primary-900 hover:underline">{p.product_name}</Link>
            ) : (
              <span className="font-medium text-primary-900">{p.product_name}</span>
            )}
            {chip && <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${chip.cls}`}>{chip.text}</span>}
          </div>
          <p className="text-xs text-neutral-500">{p.category_name}</p>
          {p.warehouses.length > 0 && (
            <p className="mt-1 text-sm text-neutral-600">
              {p.warehouses.map((w, i) => (
                <span key={`${w.location_id}-${w.family}`}>
                  {i > 0 && <span className="text-neutral-300"> · </span>}
                  {w.location_name} <strong className="text-neutral-800">{num(w.amount)} {w.amount_unit}</strong>
                </span>
              ))}
            </p>
          )}
        </div>
        <div className="text-right">
          <p className="font-display text-2xl font-semibold text-primary-900">{available}</p>
          <p className="text-xs text-neutral-500">available to sell</p>
          {reserved.map((t) => (
            <p key={t.family} className="text-xs text-neutral-500">
              <strong className="text-neutral-700">{num(t.reserved_amount)} {t.amount_unit}</strong> reserved for orders
            </p>
          ))}
        </div>
      </div>

      {expiring && (
        <div className="flex flex-wrap items-center gap-3 border-t border-neutral-100 bg-status-warningLight/40 px-4 py-2 text-sm">
          <span className="text-status-warning">
            {num(expiring.amount)} {expiring.amount_unit} · {expiryPhrase(expiring.days_left)}
          </span>
          {canAdjust && (
            <button type="button" onClick={() => openDialog("remove", "Expired")} className="font-semibold text-primary-800 hover:underline">
              Remove stock
            </button>
          )}
          <Link href={history} className="font-semibold text-primary-800 hover:underline">View stock</Link>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 border-t border-neutral-100 px-4 py-2">
        {canReceive && (
          <button
            type="button"
            onClick={() => openDialog("add")}
            className="min-h-[36px] rounded bg-primary-800 px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-700"
          >
            + Add stock
          </button>
        )}
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            aria-label={`More actions for ${p.product_name}`}
            className="min-h-[36px] rounded border border-neutral-300 px-3 py-1.5 text-sm font-semibold text-neutral-600 hover:bg-neutral-50"
          >
            ⋯
          </button>
          {menuOpen && (
            <div role="menu" className="absolute left-0 top-full z-20 mt-1 w-48 rounded border border-neutral-200 bg-white py-1 shadow-lg">
              {menuItems.map((item) => (
                <button
                  key={item.label}
                  role="menuitem"
                  type="button"
                  onClick={() => { setMenuOpen(false); item.onClick(); }}
                  className="block w-full px-3 py-2 text-left text-sm text-neutral-800 hover:bg-neutral-50"
                >
                  {item.label}
                </button>
              ))}
              <Link href={history} role="menuitem" className="block px-3 py-2 text-sm text-neutral-800 hover:bg-neutral-50">Stock details</Link>
            </div>
          )}
        </div>
      </div>

      {openError && (
        <p role="alert" className="border-t border-neutral-100 px-4 py-2 text-sm text-status-danger">{openError}</p>
      )}

      {sizesOpen && <SizesTable product={p} onChanged={onChanged} />}

      {dialog === "add" && (
        <AddStockDialog
          product={fresh ?? p}
          onClose={() => setDialog(null)}
          onDone={(message) => { onNotice({ message }); onChanged(); }}
        />
      )}
      {dialog === "correct" && <CorrectStockDialog product={fresh ?? p} onClose={() => setDialog(null)} onDone={done} />}
      {dialog === "remove" && <RemoveStockAmountDialog product={fresh ?? p} initialReason={removeReason} onClose={() => setDialog(null)} onDone={done} />}
      {dialog === "move" && <MoveStockDialog product={fresh ?? p} onClose={() => setDialog(null)} onDone={done} />}
    </div>
  );
}

/** Layer 2: each size's packs and, for operations staff, stock kept for one size only. */
function SizesTable({ product: p, onChanged }: { product: ProductStockItem; onChanged: () => void }) {
  const { getAccessToken, user } = useAuth();
  const canAdjust = !!(user && hasPermission(user.roles, "inventory.adjust"));
  const [inputs, setInputs] = useState<Record<number, string>>({});
  const [savingId, setSavingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Sizes that can be assigned a share: weight / volume / counted, 2+ per family.
  const familyCount: Record<string, number> = {};
  for (const v of p.variants) {
    const f = FAMILY[v.pack_unit]?.[0];
    if (f) familyCount[f] = (familyCount[f] ?? 0) + 1;
  }
  const assignable = (unit: string) => {
    const f = FAMILY[unit]?.[0];
    return canAdjust && !!f && familyCount[f] >= 2;
  };
  const totalFor = (unit: string) => p.totals.find((t) => t.family === FAMILY[unit]?.[0]);
  const shown = (id: number, share: string) => inputs[id] ?? (Number(share) > 0 ? num(share) : "");

  const assign = async (variantId: number, unit: string) => {
    const token = getAccessToken();
    if (!token) return;
    const [, apiUnit] = TYPED[FAMILY[unit][0]];
    setSavingId(variantId);
    setError(null);
    try {
      await setStockShares(token, p.product_id, [
        { variant_id: variantId, amount: String(Number(inputs[variantId] || 0)), amount_unit: apiUnit },
      ]);
      setInputs({});
      onChanged();
    } catch (err) {
      setError(stockErrorMessage(err, "assign this stock"));
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="border-t border-neutral-100">
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-neutral-400">
          <tr>
            <th className="px-4 py-1.5 font-medium">Size</th>
            {canAdjust && <th className="px-4 py-1.5 font-medium">Kept for this size only</th>}
            <th className="px-4 py-1.5 text-right font-medium">Packs left</th>
            <th className="px-4 py-1.5 text-right font-medium">Amount</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-50">
          {p.variants.map((v) => {
            const can = assignable(v.pack_unit);
            const family = FAMILY[v.pack_unit]?.[0];
            const [label, , base] = family ? TYPED[family] : ["", "", 1];
            const raw = shown(v.variant_id, v.share_amount);
            const changed = can && Number(raw || 0) !== Number(v.share_amount);
            const size = Number(v.pack_quantity) * (FAMILY[v.pack_unit]?.[1] ?? 1);
            const packsFromInput = can ? Math.floor(((Number(raw) || 0) * base) / size + 1e-9) : 0;
            const unassigned = Number(totalFor(v.pack_unit)?.unassigned_amount ?? 0);
            const tooMuch = changed && Number(raw || 0) - Number(v.share_amount) > unassigned + 0.0005;
            return (
              <tr key={v.variant_id}>
                <td className="px-4 py-2">
                  <span className="font-medium text-neutral-800">{v.variant_name}</span>
                  <span className="ml-2 text-xs text-neutral-400">pack of {packSize(v.pack_quantity, v.pack_unit)}</span>
                </td>
                {canAdjust && (
                  <td className="px-4 py-2">
                    {can ? (
                      <div>
                        <div className="flex items-center gap-1.5">
                          <input
                            type="number"
                            min="0"
                            step="any"
                            value={raw}
                            onChange={(e) => setInputs((cur) => ({ ...cur, [v.variant_id]: e.target.value }))}
                            placeholder="0"
                            aria-label={`${v.variant_name} kept ${label}`}
                            className="w-20 rounded border border-neutral-300 px-2 py-1 text-right text-sm"
                          />
                          <span className="text-xs text-neutral-500">{label}</span>
                          {changed && (
                            <button
                              type="button"
                              onClick={() => assign(v.variant_id, v.pack_unit)}
                              disabled={savingId !== null || tooMuch}
                              className="rounded bg-primary-800 px-2 py-1 text-xs font-semibold text-white disabled:opacity-40"
                            >
                              {savingId === v.variant_id ? "Saving..." : "Save"}
                            </button>
                          )}
                        </div>
                        <p className={`mt-0.5 text-xs ${tooMuch ? "text-status-danger" : "text-neutral-400"}`}>
                          {tooMuch
                            ? `Only ${plain(unassigned)} ${label} is shared by all sizes right now`
                            : `= ${packCount(changed ? packsFromInput : v.share_packs)} of its own`}
                        </p>
                      </div>
                    ) : (
                      <span className="text-xs text-neutral-300">—</span>
                    )}
                  </td>
                )}
                <td className={`px-4 py-2 text-right ${Number(v.available_packs) === 0 ? "font-semibold text-status-danger" : "text-neutral-800"}`}>
                  {packCount(v.available_packs)}
                </td>
                <td className="px-4 py-2 text-right text-neutral-600">{num(v.available_amount)} {v.amount_unit}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {error && (
        <p role="alert" className="mx-4 mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>
      )}
    </div>
  );
}
