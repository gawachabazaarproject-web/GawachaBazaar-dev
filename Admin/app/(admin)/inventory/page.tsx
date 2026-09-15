"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
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

const PAGE_SIZE = 20;

export default function InventoryPage() {
  const { getAccessToken, user } = useAuth();
  const router = useRouter();

  const [dashboard, setDashboard] = useState<InventoryDashboard | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [data, setData] = useState<AdminInventoryLotListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [receiveOpen, setReceiveOpen] = useState(false);

  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
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
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAdminLots(token, {
        page,
        page_size: PAGE_SIZE,
        q: q || undefined,
        location_id: locationId ? Number(locationId) : undefined,
        category_id: categoryId ? Number(categoryId) : undefined,
        operational_status: operationalStatus || undefined,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof InventoryApiError ? err.message : "Unable to load inventory.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, q, locationId, categoryId, operationalStatus]);

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
            <button onClick={() => setReceiveOpen(true)} className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700">
              Receive stock
            </button>
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

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded border border-neutral-200 bg-white p-3">
        <input
          value={q}
          onChange={(e) => { setPage(1); setQ(e.target.value); }}
          placeholder="Product name, SKU, or batch code"
          className="min-w-[220px] flex-1 rounded border border-neutral-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
        <select value={locationId} onChange={(e) => { setPage(1); setLocationId(e.target.value); }} className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-700">
          <option value="">Warehouse: All</option>
          {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
        </select>
        <select value={categoryId} onChange={(e) => { setPage(1); setCategoryId(e.target.value); }} className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-700">
          <option value="">Category: All</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select value={operationalStatus} onChange={(e) => { setPage(1); setOperationalStatus(e.target.value); }} className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-700">
          <option value="">Status: All</option>
          {OPERATIONAL_STATUSES.map((s) => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}
        </select>
        {hasFilters && (
          <button onClick={clearFilters} className="text-sm font-medium text-primary-700 hover:underline">
            Clear filters
          </button>
        )}
      </div>

      <div className="overflow-hidden rounded border border-neutral-200 bg-white">
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
                    <th className="px-4 py-2 font-medium">Last movement</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {data.items.map((lot) => (
                    <LotRow key={lot.id} lot={lot} onClick={() => router.push(`/inventory/${lot.id}`)} />
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
          </>
        )}
      </div>

      <ReceiveStockDialog open={receiveOpen} onClose={() => setReceiveOpen(false)} onReceived={refreshAll} />
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

function LotRow({ lot, onClick }: { lot: AdminInventoryLotListItem; onClick: () => void }) {
  return (
    <tr onClick={onClick} className="cursor-pointer hover:bg-neutral-50">
      <td className="px-4 py-3">
        <p className="font-medium text-primary-900">{lot.product_name}</p>
        <p className="text-xs text-neutral-500">{lot.sku}</p>
      </td>
      <td className="px-4 py-3 text-neutral-600">{lot.category_name}</td>
      <td className="px-4 py-3 text-neutral-600">{lot.location_name}</td>
      <td className="px-4 py-3">
        <p className="text-neutral-700">{lot.batch_code}</p>
        {lot.batch_expiry_date && <p className="text-xs text-neutral-400">exp {lot.batch_expiry_date}</p>}
      </td>
      <td className="px-4 py-3 text-right text-neutral-600">{lot.on_hand}</td>
      <td className="px-4 py-3 text-right text-neutral-600">{lot.reserved}</td>
      <td className="px-4 py-3 text-right font-semibold text-primary-900">{lot.available}</td>
      <td className="px-4 py-3"><StatusBadge status={lot.operational_status} /></td>
      <td className="px-4 py-3 text-neutral-500">{lot.last_movement_at ? formatDateTime(lot.last_movement_at) : "—"}</td>
    </tr>
  );
}
