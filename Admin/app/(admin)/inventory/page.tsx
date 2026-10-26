"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { readInitialQuery, useDebounced, useUrlQuerySync } from "@/lib/use-list-query";
import { hasPermission } from "@/lib/permissions";
import {
  AdminInventoryLotListItem,
  AdminInventoryLotListResponse,
  fetchAdminLots,
  fetchLocations,
  fetchProductStockSummary,
  InventoryApiError,
  Location,
  OPERATIONAL_STATUSES,
  packCount,
  packTotal,
  ProductStockOperation,
  ProductStockSummary,
  StockFilter,
} from "@/lib/inventory";
import { Category, fetchCategories } from "@/lib/products";
import { formatDateTime } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { Pagination } from "@/components/Pagination";
import { StatusBadge } from "@/components/StatusBadge";
import { ReceiveStockDialog } from "@/components/ReceiveStockDialog";
import { AddWarehouseDialog } from "@/components/AddWarehouseDialog";
import { RemoveStockDialog } from "@/components/RemoveStockDialog";
import { ProductStockView } from "@/components/ProductStockView";
import { StockActionBanner, StockNotice } from "@/components/StockActionBanner";
import { SearchableSelect, categoryOptions } from "@/components/SearchableSelect";

const PAGE_SIZE = 20;

const CHIPS: { key: StockFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "low", label: "Low" },
  { key: "out", label: "Out" },
  { key: "expiring", label: "Expiring" },
];

export default function InventoryPage() {
  const { getAccessToken, user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [categories, setCategories] = useState<Category[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [summary, setSummary] = useState<ProductStockSummary | null>(null);
  const [notice, setNotice] = useState<StockNotice | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [receiveOpen, setReceiveOpen] = useState(false);
  const [warehouseOpen, setWarehouseOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  // "Stock details" (lots, batches, movements) is the second layer: it is
  // reached from a card or the More menu, never the first thing staff see.
  const [view, setView] = useState<"product" | "lot">(searchParams.get("view") === "lot" ? "lot" : "product");
  const [filter, setFilter] = useState<StockFilter>("all");
  const [q, setQ] = useState(readInitialQuery);
  const dq = useDebounced(q);
  useUrlQuerySync((v) => { setPage(1); setQ(v); });
  const [categoryId, setCategoryId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [operationalStatus, setOperationalStatus] = useState("");
  const [page, setPage] = useState(1);

  const canReceive = !!(user && hasPermission(user.roles, "inventory.receive"));
  const canAdjust = !!(user && hasPermission(user.roles, "inventory.adjust"));

  const [data, setData] = useState<AdminInventoryLotListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<AdminInventoryLotListItem | null>(null);
  const hasFilters = Boolean(q || locationId || categoryId || operationalStatus);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    fetchCategories().then(setCategories).catch(() => undefined);
    fetchLocations(token).then(setLocations).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadSummary = useCallback(() => {
    const token = getAccessToken();
    if (!token) return;
    fetchProductStockSummary(token, { q: dq || undefined, category_id: categoryId ? Number(categoryId) : undefined })
      .then(setSummary)
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dq, categoryId]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary, reloadKey]);

  useEffect(() => {
    if (!moreOpen) return;
    const close = (e: MouseEvent) => {
      if (!moreRef.current?.contains(e.target as Node)) setMoreOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [moreOpen]);

  const loadLots = useCallback(async () => {
    const token = getAccessToken();
    if (!token || view !== "lot") return;
    setLoading(true);
    setError(null);
    try {
      setData(
        await fetchAdminLots(token, {
          page,
          page_size: PAGE_SIZE,
          q: dq || undefined,
          location_id: locationId ? Number(locationId) : undefined,
          category_id: categoryId ? Number(categoryId) : undefined,
          operational_status: operationalStatus || undefined,
        }),
      );
    } catch (err) {
      setError(err instanceof InventoryApiError ? err.message : "Couldn't load the stock details. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, page, dq, locationId, categoryId, operationalStatus, reloadKey]);

  useEffect(() => {
    loadLots();
  }, [loadLots]);

  const refresh = () => setReloadKey((k) => k + 1);
  const clearFilters = () => {
    setQ("");
    setLocationId("");
    setCategoryId("");
    setOperationalStatus("");
  };
  const showNotice = (n: StockNotice) => setNotice(n);
  const afterUndo = (_op?: ProductStockOperation) => refresh();

  return (
    <div>
      <PageHeader
        eyebrow="Operations"
        title="Inventory"
        description="What do we have, and what needs doing."
        actions={
          <div className="flex items-center gap-2">
            {canReceive && (
              <button
                type="button"
                onClick={() => setReceiveOpen(true)}
                className="min-h-[40px] rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700"
              >
                + Receive stock
              </button>
            )}
            <div className="relative" ref={moreRef}>
              <button
                type="button"
                onClick={() => setMoreOpen((o) => !o)}
                aria-haspopup="menu"
                aria-expanded={moreOpen}
                className="min-h-[40px] rounded border border-neutral-300 px-3 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50"
              >
                More ▾
              </button>
              {moreOpen && (
                <div role="menu" className="absolute right-0 top-full z-20 mt-1 w-56 rounded border border-neutral-200 bg-white py-1 shadow-lg">
                  <button role="menuitem" type="button" onClick={() => { setMoreOpen(false); setView(view === "lot" ? "product" : "lot"); setPage(1); }} className="block w-full px-3 py-2 text-left text-sm hover:bg-neutral-50">
                    {view === "lot" ? "Back to products" : "Stock by warehouse & batch"}
                  </button>
                  <button role="menuitem" type="button" onClick={() => { setMoreOpen(false); router.push("/inventory/alerts"); }} className="block w-full px-3 py-2 text-left text-sm hover:bg-neutral-50">
                    Restock list
                  </button>
                  {canReceive && (
                    <button role="menuitem" type="button" onClick={() => { setMoreOpen(false); setWarehouseOpen(true); }} className="block w-full px-3 py-2 text-left text-sm hover:bg-neutral-50">
                      Add warehouse
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        }
      />

      {notice && (
        <StockActionBanner
          notice={notice}
          historyHref={`/inventory?view=lot&q=${encodeURIComponent(q)}`}
          onChanged={afterUndo}
          onDismiss={() => setNotice(null)}
        />
      )}

      {view === "product" && (
        <div className="mb-3 flex flex-wrap gap-2" role="tablist" aria-label="Show">
          {CHIPS.map((chip) => {
            const count = summary ? summary[chip.key] : null;
            const active = filter === chip.key;
            const urgent = (chip.key === "out" || chip.key === "low" || chip.key === "expiring") && count !== null && count > 0;
            return (
              <button
                key={chip.key}
                role="tab"
                aria-selected={active}
                type="button"
                onClick={() => setFilter(chip.key)}
                className={`min-h-[36px] rounded-full border px-3.5 py-1 text-sm font-medium ${
                  active ? "border-primary-800 bg-primary-800 text-white" : "border-neutral-200 bg-white text-neutral-700 hover:bg-neutral-50"
                }`}
              >
                {chip.label}
                {count !== null && (
                  <span className={`ml-1.5 ${active ? "text-white/80" : urgent ? "font-semibold text-status-danger" : "text-neutral-400"}`}>{count}</span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {view === "lot" && (
        <div className="mb-3 flex items-center gap-3 text-sm">
          <button type="button" onClick={() => setView("product")} className="font-semibold text-primary-700 hover:underline">← Back to products</button>
          <span className="text-neutral-500">Stock by warehouse &amp; batch</span>
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded border border-neutral-200 bg-white p-3">
        <input
          value={q}
          onChange={(e) => { setPage(1); setQ(e.target.value); }}
          placeholder={view === "product" ? "Search products..." : "Product name, SKU, or batch code"}
          aria-label="Search"
          className="min-w-[220px] flex-1 rounded border border-neutral-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
        {view === "lot" && (
          <SearchableSelect
            className="w-52"
            value={locationId}
            onChange={(v) => { setPage(1); setLocationId(v); }}
            placeholder="Warehouse: All"
            options={locations.map((l) => ({ value: String(l.id), label: l.name }))}
          />
        )}
        <SearchableSelect
          className="w-56"
          value={categoryId}
          onChange={(v) => { setPage(1); setCategoryId(v); }}
          placeholder="Category: All"
          options={categoryOptions(categories)}
        />
        {view === "lot" && (
          <select value={operationalStatus} onChange={(e) => { setPage(1); setOperationalStatus(e.target.value); }} className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-700" aria-label="Status">
            <option value="">Status: All</option>
            {OPERATIONAL_STATUSES.map((s) => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}
          </select>
        )}
        {hasFilters && (
          <button type="button" onClick={clearFilters} className="text-sm font-medium text-primary-700 hover:underline">
            Clear filters
          </button>
        )}
      </div>

      {view === "product" && (
        <ProductStockView q={dq} categoryId={categoryId} filter={filter} reloadKey={reloadKey} onNotice={showNotice} onChanged={refresh} />
      )}

      {view === "lot" && (
        <div className="overflow-hidden rounded border border-neutral-200 bg-white">
          {loading && !data ? (
            <TableSkeleton rows={8} columns={9} />
          ) : error ? (
            <ErrorState message={error} onRetry={loadLots} />
          ) : !data || data.items.length === 0 ? (
            <EmptyState
              icon="box"
              title={hasFilters ? "No stock matches these filters" : "No stock yet"}
              message={hasFilters ? "Try a different search or clear filters." : "Receive stock to get started."}
              action={hasFilters ? <button type="button" onClick={clearFilters} className="text-sm font-semibold text-primary-700 hover:underline">Clear filters</button> : undefined}
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                    <tr>
                      <th className="px-4 py-2 font-medium">Product</th>
                      <th className="px-4 py-2 font-medium">Warehouse</th>
                      <th className="px-4 py-2 font-medium">Delivery</th>
                      <th className="px-4 py-2 text-right font-medium">In stock</th>
                      <th className="px-4 py-2 text-right font-medium">Reserved</th>
                      <th className="px-4 py-2 text-right font-medium">Available</th>
                      <th className="px-4 py-2 font-medium">Status</th>
                      <th className="px-4 py-2 font-medium">Last change</th>
                      {canAdjust && <th className="px-4 py-2" />}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {data.items.map((lot) => (
                      <LotRow key={lot.id} lot={lot} onClick={() => router.push(`/inventory/${lot.id}`)} onRemove={canAdjust ? () => setRemoving(lot) : undefined} />
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
            </>
          )}
        </div>
      )}

      <ReceiveStockDialog
        open={receiveOpen}
        onClose={() => setReceiveOpen(false)}
        onDone={(message) => { showNotice({ message }); refresh(); }}
      />
      <RemoveStockDialog open={removing !== null} lot={removing} onClose={() => setRemoving(null)} onDone={refresh} />
      <AddWarehouseDialog
        open={warehouseOpen}
        onClose={() => setWarehouseOpen(false)}
        onCreated={() => {
          const token = getAccessToken();
          if (token) fetchLocations(token).then(setLocations).catch(() => undefined);
        }}
      />
    </div>
  );
}

function LotRow({ lot, onClick, onRemove }: { lot: AdminInventoryLotListItem; onClick: () => void; onRemove?: () => void }) {
  return (
    <tr onClick={onClick} className="cursor-pointer hover:bg-neutral-50">
      <td className="px-4 py-3">
        <p className="font-medium text-primary-900">
          {lot.product_name}
          <span className="ml-2 rounded-full bg-neutral-100 px-2 py-0.5 text-xs font-semibold text-neutral-600">
            {lot.variant_name}
          </span>
        </p>
        <p className="text-xs text-neutral-500">{lot.category_name}</p>
      </td>
      <td className="px-4 py-3 text-neutral-600">{lot.location_name}</td>
      <td className="px-4 py-3">
        <p className="text-neutral-700">{lot.batch_code}</p>
        {lot.batch_expiry_date && <p className="text-xs text-neutral-400">expires {lot.batch_expiry_date}</p>}
      </td>
      <td className="px-4 py-3 text-right text-neutral-600">
        {packCount(lot.on_hand)}
        <p className="text-xs text-neutral-400">{packTotal(lot.on_hand, lot.variant_quantity, lot.variant_unit)}</p>
      </td>
      <td className="px-4 py-3 text-right text-neutral-600">{packCount(lot.reserved)}</td>
      <td className="px-4 py-3 text-right font-semibold text-primary-900">
        {packCount(lot.available)}
        <p className="text-xs font-normal text-neutral-400">{packTotal(lot.available, lot.variant_quantity, lot.variant_unit)}</p>
      </td>
      <td className="px-4 py-3"><StatusBadge status={lot.operational_status} /></td>
      <td className="px-4 py-3 text-neutral-500">{lot.last_movement_at ? formatDateTime(lot.last_movement_at) : "—"}</td>
      {onRemove && (
        <td className="px-4 py-3 text-right">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            disabled={Number(lot.available) <= 0}
            className="text-xs font-semibold text-status-danger hover:underline disabled:text-neutral-300 disabled:no-underline"
          >
            Remove
          </button>
        </td>
      )}
    </tr>
  );
}
