"use client";

import React, { useCallback, useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { readInitialQuery, useDebounced, useUrlQuerySync } from "@/lib/use-list-query";
import { hasPermission } from "@/lib/permissions";
import {
  AdminInventoryLotListItem,
  AdminInventoryLotListResponse,
  fetchAdminLots,
  fetchDashboard,
  fetchLocations,
  InventoryApiError,
  InventoryDashboard,
  Location,
  OPERATIONAL_STATUSES,
  packCount,
  packTotal,
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
import { SearchableSelect, categoryOptions } from "@/components/SearchableSelect";

const PAGE_SIZE = 20;

export default function InventoryPage() {
  const { getAccessToken, user } = useAuth();
  const router = useRouter();

  const [dashboard, setDashboard] = useState<InventoryDashboard | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [data, setData] = useState<AdminInventoryLotListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  // After the first load, refreshes are silent so the page does not blank out.
  const loadedOnce = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [receiveOpen, setReceiveOpen] = useState(false);
  const [warehouseOpen, setWarehouseOpen] = useState(false);
  const [removing, setRemoving] = useState<AdminInventoryLotListItem | null>(null);
  const canAdjust = user && hasPermission(user.roles, "inventory.adjust");

  const [page, setPage] = useState(1);
  const [q, setQ] = useState(readInitialQuery);
  const dq = useDebounced(q);
  useUrlQuerySync((v) => { setPage(1); setQ(v); });
  const [view, setView] = useState<"product" | "lot">("product");
  const [locationId, setLocationId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [operationalStatus, setOperationalStatus] = useState("");
  const hasFilters = Boolean(q || locationId || categoryId || operationalStatus);

  const canReceive = user && hasPermission(user.roles, "inventory.receive");

  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    fetchDashboard(token).then(setDashboard).catch(() => undefined);
    fetchCategories().then(setCategories).catch(() => undefined);
    fetchLocations(token).then(setLocations).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    if (!loadedOnce.current) setLoading(true); // refreshes after an edit stay in place
    setError(null);
    try {
      const result = await fetchAdminLots(token, {
        page,
        page_size: PAGE_SIZE,
        q: dq || undefined,
        location_id: locationId ? Number(locationId) : undefined,
        category_id: categoryId ? Number(categoryId) : undefined,
        operational_status: operationalStatus || undefined,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof InventoryApiError ? err.message : "Unable to load inventory.");
    } finally {
      setLoading(false);
      loadedOnce.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, dq, locationId, categoryId, operationalStatus]);

  useEffect(() => {
    load();
  }, [load]);

  const refreshAll = () => {
    const token = getAccessToken();
    if (token) fetchDashboard(token).then(setDashboard).catch(() => undefined);
    load();
  };

  const clearFilters = () => {
    setQ("");
    setLocationId("");
    setCategoryId("");
    setOperationalStatus("");
  };

  return (
    <div>
      <PageHeader
        eyebrow="Operations"
        title="Inventory"
        description="On-hand, reserved, and available stock across every warehouse - transactional, never a raw quantity edit."
        actions={
          canReceive ? (
            <div className="flex gap-2">
              <button onClick={() => setWarehouseOpen(true)} className="rounded border border-primary-800 px-4 py-2 text-sm font-semibold text-primary-800 hover:bg-primary-50">
                Add warehouse
              </button>
              <button onClick={() => setReceiveOpen(true)} className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700">
                Receive stock
              </button>
            </div>
          ) : undefined
        }
      />

      {dashboard && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          <Metric label="SKUs" value={dashboard.total_skus} />
          <Metric label="On hand" value={dashboard.total_on_hand} />
          <Metric label="Reserved" value={dashboard.total_reserved} />
          <Metric label="Available" value={dashboard.total_available} emphasize />
          <Metric
            label="Low stock"
            value={dashboard.low_stock_count}
            tone={dashboard.low_stock_count > 0 ? "warning" : undefined}
            onClick={() => setOperationalStatus("LOW_STOCK")}
          />
          <Metric
            label="Out of stock"
            value={dashboard.out_of_stock_count}
            tone={dashboard.out_of_stock_count > 0 ? "danger" : undefined}
            onClick={() => setOperationalStatus("OUT_OF_STOCK")}
          />
          <Metric
            label="Expiring/expired"
            value={dashboard.expiring_batches_count + dashboard.expired_batches_count}
            tone={dashboard.expiring_batches_count + dashboard.expired_batches_count > 0 ? "warning" : undefined}
          />
        </div>
      )}

      <div className="mb-3 inline-flex rounded border border-neutral-300 bg-white p-0.5 text-sm font-semibold">
        {([["product", "By product"], ["lot", "By lot / warehouse"]] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setView(key)}
            className={`rounded px-3 py-1 ${view === key ? "bg-primary-800 text-white" : "text-neutral-600 hover:bg-neutral-50"}`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded border border-neutral-200 bg-white p-3">
        <input
          value={q}
          onChange={(e) => { setPage(1); setQ(e.target.value); }}
          placeholder={view === "product" ? "Product name" : "Product name, SKU, or batch code"}
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
          <select value={operationalStatus} onChange={(e) => { setPage(1); setOperationalStatus(e.target.value); }} className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-700">
            <option value="">Status: All</option>
            {OPERATIONAL_STATUSES.map((s) => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}
          </select>
        )}
        {hasFilters && (
          <button onClick={clearFilters} className="text-sm font-medium text-primary-700 hover:underline">
            Clear filters
          </button>
        )}
      </div>

      {view === "product" && <ProductStockView q={dq} categoryId={categoryId} />}

      {view === "lot" && <div className="overflow-hidden rounded border border-neutral-200 bg-white">
        {loading ? (
          <TableSkeleton rows={8} columns={9} />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon="box"
            title={hasFilters ? "No inventory matches these filters" : "No inventory yet"}
            message={hasFilters ? "Try a different search or clear filters." : "Receive stock to get started."}
            action={hasFilters ? <button onClick={clearFilters} className="text-sm font-semibold text-primary-700 hover:underline">Clear filters</button> : undefined}
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                  <tr>
                    <th className="px-4 py-2 font-medium">Product</th>
                    <th className="px-4 py-2 font-medium">Category</th>
                    <th className="px-4 py-2 font-medium">Warehouse</th>
                    <th className="px-4 py-2 font-medium">Batch</th>
                    <th className="px-4 py-2 text-right font-medium">On hand</th>
                    <th className="px-4 py-2 text-right font-medium">Reserved</th>
                    <th className="px-4 py-2 text-right font-medium">Available</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 text-right font-medium">Reserve</th>
                    <th className="px-4 py-2 font-medium">Last movement</th>
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
      </div>}

      <ReceiveStockDialog open={receiveOpen} onClose={() => setReceiveOpen(false)} onReceived={refreshAll} />
      <RemoveStockDialog open={removing !== null} lot={removing} onClose={() => setRemoving(null)} onDone={refreshAll} />
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

function Metric({
  label,
  value,
  emphasize,
  tone,
  onClick,
}: {
  label: string;
  value: number | string;
  emphasize?: boolean;
  tone?: "warning" | "danger";
  onClick?: () => void;
}) {
  const toneClass = tone === "danger" ? "text-status-danger" : tone === "warning" ? "text-status-warning" : "text-primary-900";
  return (
    <button
      onClick={onClick}
      disabled={!onClick}
      className={`rounded border border-neutral-200 bg-white p-3 text-left ${onClick ? "cursor-pointer hover:border-primary-300" : "cursor-default"}`}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">{label}</p>
      <p className={`mt-1 font-display text-xl font-semibold ${emphasize ? "text-primary-900" : toneClass}`}>{value}</p>
    </button>
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
        <p className="text-xs text-neutral-500">{lot.sku}</p>
      </td>
      <td className="px-4 py-3 text-neutral-600">{lot.category_name}</td>
      <td className="px-4 py-3 text-neutral-600">{lot.location_name}</td>
      <td className="px-4 py-3">
        <p className="text-neutral-700">{lot.batch_code}</p>
        {lot.batch_expiry_date && <p className="text-xs text-neutral-400">exp {lot.batch_expiry_date}</p>}
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
      <td className="px-4 py-3 text-right text-neutral-600">{lot.effective_reserve !== null ? Number(lot.effective_reserve) : "—"}</td>
      <td className="px-4 py-3 text-neutral-500">{lot.last_movement_at ? formatDateTime(lot.last_movement_at) : "—"}</td>
      {onRemove && (
        <td className="px-4 py-3 text-right">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            disabled={Number(lot.available) <= 0}
            className="text-xs font-semibold text-status-danger hover:underline disabled:text-neutral-300 disabled:no-underline"
          >
            Remove stock
          </button>
        </td>
      )}
    </tr>
  );
}
