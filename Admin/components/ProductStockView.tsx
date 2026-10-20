"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  fetchProductStock,
  InventoryApiError,
  packCount,
  packSize,
  ProductStockItem,
  ProductStockListResponse,
  setStockShares,
} from "@/lib/inventory";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Pagination } from "@/components/Pagination";
import { TableSkeleton } from "@/components/TableSkeleton";

const PAGE_SIZE = 20;
const num = (v: string | number) => String(Number(Number(v).toFixed(3)));

// pack unit -> [unit family, size of one unit in the family's base unit]
const FAMILY: Record<string, [string, number]> = {
  KG: ["MASS", 1000], G: ["MASS", 1], L: ["VOLUME", 1000], ML: ["VOLUME", 1], UNIT: ["COUNT", 1], DOZEN: ["COUNT", 12],
};
// What an assigned share is typed in, per family: [label, API unit, base units per typed unit].
const TYPED: Record<string, [string, string, number]> = {
  MASS: ["kg", "KG", 1000], VOLUME: ["L", "L", 1000], COUNT: ["pieces", "UNIT", 1],
};

/** Inventory by product: the stock total ("34 kg") with each size's packs
 * and weight underneath. Stock can be assigned to a size right in the card;
 * what is not assigned stays shared by every size. */
export function ProductStockView({ q, categoryId }: { q: string; categoryId: string }) {
  const { getAccessToken } = useAuth();
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ProductStockListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setPage(1), [q, categoryId]);

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
        }),
      );
    } catch (err) {
      setError(err instanceof InventoryApiError ? err.message : "Unable to load stock by product.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, q, categoryId]);

  useEffect(() => {
    load();
  }, [load]);

  const replaceItem = (item: ProductStockItem) =>
    setData((d) => (d ? { ...d, items: d.items.map((p) => (p.product_id === item.product_id ? item : p)) } : d));

  if (loading) return <div className="rounded border border-neutral-200 bg-white"><TableSkeleton rows={6} columns={3} /></div>;
  if (error) return <div className="rounded border border-neutral-200 bg-white"><ErrorState message={error} onRetry={load} /></div>;
  if (!data || data.items.length === 0) {
    return (
      <div className="rounded border border-neutral-200 bg-white">
        <EmptyState icon="box" title="No products found" message="Try a different search or category." />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {data.items.map((p) => (
        <ProductCard
          key={p.product_id}
          product={p}
          onChanged={replaceItem}
          onOpen={() => router.push(`/products/${p.product_id}`)}
        />
      ))}
      <div className="rounded border border-neutral-200 bg-white">
        <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
      </div>
    </div>
  );
}

function ProductCard({
  product: p,
  onChanged,
  onOpen,
}: {
  product: ProductStockItem;
  onChanged: (item: ProductStockItem) => void;
  onOpen: () => void;
}) {
  const { getAccessToken, user } = useAuth();
  const canAdjust = !!(user && hasPermission(user.roles, "inventory.adjust"));
  const [expanded, setExpanded] = useState(false);
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
      const updated = await setStockShares(token, p.product_id, [
        { variant_id: variantId, amount: String(Number(inputs[variantId] || 0)), amount_unit: apiUnit },
      ]);
      setInputs({});
      onChanged(updated);
    } catch (err) {
      setError(err instanceof InventoryApiError ? err.message : "Unable to assign this stock.");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="rounded border border-neutral-200 bg-white">
      <div
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        onClick={() => setExpanded((e) => !e)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setExpanded((x) => !x);
          }
        }}
        className={`flex cursor-pointer items-start justify-between gap-4 px-4 py-3 hover:bg-neutral-50 ${expanded ? "border-b border-neutral-100" : ""}`}
      >
        <div className="flex min-w-0 items-start gap-2">
          <svg
            className={`mt-1 h-4 w-4 shrink-0 text-neutral-500 transition-transform ${expanded ? "rotate-90" : ""}`}
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden
          >
            <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.17 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
          </svg>
          <div className="min-w-0">
            <a
              href={`/products/${p.product_id}`}
              onClick={(e) => e.stopPropagation()}
              className="font-medium text-primary-900 hover:underline"
            >
              {p.product_name}
            </a>
            <p className="text-xs text-neutral-500">
              {p.category_name} · {p.variants.length} size{p.variants.length === 1 ? "" : "s"}
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs uppercase tracking-wide text-neutral-500">Total in stock</p>
          <p className="font-display text-xl font-semibold text-primary-900">
            {p.totals.length === 0 ? "—" : p.totals.map((t) => `${num(t.amount)} ${t.amount_unit}`).join(" + ")}
          </p>
          {p.totals
            .filter((t) => familyCount[t.family] >= 2)
            .map((t) => (
              <p key={t.family} className="text-xs text-neutral-500">
                Unassigned <strong className="text-neutral-800">{num(t.unassigned_amount)} {t.amount_unit}</strong>
                <span className="text-neutral-400"> · shared by all sizes</span>
              </p>
            ))}
        </div>
      </div>
      {expanded && (
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-neutral-400">
          <tr>
            <th className="px-4 py-1.5 font-medium">Size</th>
            {canAdjust && <th className="px-4 py-1.5 font-medium">Assigned to this size</th>}
            <th className="px-4 py-1.5 text-right font-medium">Packs left</th>
            <th className="px-4 py-1.5 text-right font-medium">Weight / amount</th>
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
              <tr key={v.variant_id} className="hover:bg-neutral-50">
                <td className="px-4 py-2" onClick={onOpen}>
                  <span className="font-medium text-neutral-800">{v.variant_name}</span>
                  <span className="ml-2 text-xs text-neutral-400">{v.sku} · pack of {packSize(v.pack_quantity, v.pack_unit)}</span>
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
                            aria-label={`${v.variant_name} assigned ${label}`}
                            className="w-20 rounded border border-neutral-300 px-2 py-1 text-right text-sm"
                          />
                          <span className="text-xs text-neutral-500">{label}</span>
                          {changed && (
                            <button
                              onClick={() => assign(v.variant_id, v.pack_unit)}
                              disabled={savingId !== null || tooMuch}
                              className="rounded bg-primary-800 px-2 py-1 text-xs font-semibold text-white disabled:opacity-40"
                            >
                              {savingId === v.variant_id ? "Saving..." : "Assign"}
                            </button>
                          )}
                        </div>
                        <p className={`mt-0.5 text-xs ${tooMuch ? "text-status-danger" : "text-neutral-400"}`}>
                          {tooMuch
                            ? `Only ${num(unassigned)} ${label} unassigned`
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
      )}
      {expanded && error && (
        <p className="mx-4 mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>
      )}
    </div>
  );
}
