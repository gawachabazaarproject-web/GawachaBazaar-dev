"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import { fetchStockAlerts, InventoryApiError, packCount, packTotal, StockAlertItem, StockAlerts } from "@/lib/inventory";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { ReceiveStockDialog } from "@/components/ReceiveStockDialog";

type Filter = "ALL" | "OUT" | "BELOW" | "NEAR";

const LABEL: Record<StockAlertItem["level"], string> = {
  OUT: "Out of stock",
  BELOW: "Low on stock",
  NEAR: "Close to reserve",
};
const TONE: Record<StockAlertItem["level"], string> = {
  OUT: "bg-status-dangerLight text-status-danger",
  BELOW: "bg-status-warningLight text-status-warning",
  NEAR: "bg-neutral-100 text-neutral-600",
};

/** Everything that is out of stock or running low, with how much is left,
 * how much should stay in reserve, and how much is missing to get there. */
export default function StockAlertsPage() {
  const { getAccessToken, user } = useAuth();
  const canReceive = !!(user && hasPermission(user.roles, "inventory.receive"));
  const [data, setData] = useState<StockAlerts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [receiveFor, setReceiveFor] = useState<number | null>(null);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setError(null);
    try {
      setData(await fetchStockAlerts(token, 1000));
    } catch (err) {
      setError(err instanceof InventoryApiError ? err.message : "Unable to load stock alerts.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const items = (data?.items ?? []).filter((a) => filter === "ALL" || a.level === filter);
  const tabs: [Filter, string, number][] = [
    ["ALL", "All", data?.count ?? 0],
    ["OUT", "Out of stock", data?.out_count ?? 0],
    ["BELOW", "Low on stock", data?.below_count ?? 0],
    ["NEAR", "Close to reserve", data?.near_count ?? 0],
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Operations"
        title="Stock alerts"
        description="Items that are out of stock or at, below or close to the reserve you set. Reserve is the stock you want to keep on the shelf."
        actions={
          <Link href="/inventory" className="rounded border border-primary-800 px-4 py-2 text-sm font-semibold text-primary-800 hover:bg-primary-50">
            Open inventory
          </Link>
        }
      />

      <div className="mb-4 inline-flex flex-wrap rounded border border-neutral-300 bg-white p-0.5 text-sm font-semibold">
        {tabs.map(([key, label, count]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`rounded px-3 py-1 ${filter === key ? "bg-primary-800 text-white" : "text-neutral-600 hover:bg-neutral-50"}`}
          >
            {label} <span className={filter === key ? "text-white/80" : "text-neutral-400"}>{count}</span>
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded border border-neutral-200 bg-white">
        {loading ? (
          <TableSkeleton rows={8} columns={6} />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : items.length === 0 ? (
          <EmptyState icon="box" title="Nothing to restock" message="Every item is comfortably above its reserve." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Product</th>
                  <th className="px-4 py-2 text-right font-medium">Left</th>
                  <th className="px-4 py-2 text-right font-medium">Keep in reserve</th>
                  <th className="px-4 py-2 text-right font-medium">Missing to reach reserve</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  {canReceive && <th className="px-4 py-2" />}
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {items.map((a) => {
                  const missing = Math.max(Number(a.reserve_level) - Number(a.available), 0);
                  return (
                    <tr key={a.variant_id} className="hover:bg-neutral-50">
                      <td className="px-4 py-3">
                        <Link href={`/products/${a.product_id}`} className="font-medium text-primary-900 hover:underline">
                          {a.product_name}
                        </Link>
                        <p className="text-xs text-neutral-500">{a.variant_name}</p>
                      </td>
                      <td className={`px-4 py-3 text-right ${a.level === "OUT" ? "font-semibold text-status-danger" : "text-neutral-800"}`}>
                        {packCount(a.available)}
                        <p className="text-xs font-normal text-neutral-400">{packTotal(a.available, a.pack_quantity, a.unit)}</p>
                      </td>
                      <td className="px-4 py-3 text-right text-neutral-700">
                        {packCount(a.reserve_level)}
                        <p className="text-xs text-neutral-400">{packTotal(a.reserve_level, a.pack_quantity, a.unit)}</p>
                      </td>
                      <td className="px-4 py-3 text-right text-neutral-700">
                        {missing > 0 ? (
                          <>
                            {packCount(missing)}
                            <p className="text-xs text-neutral-400">{packTotal(missing, a.pack_quantity, a.unit)}</p>
                          </>
                        ) : (
                          <span className="text-neutral-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${TONE[a.level]}`}>{LABEL[a.level]}</span>
                      </td>
                      {canReceive && (
                        <td className="px-4 py-3 text-right">
                          <button onClick={() => setReceiveFor(a.product_id)} className="text-xs font-semibold text-primary-700 hover:underline">
                            Receive stock
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ReceiveStockDialog
        open={receiveFor !== null}
        initialProductId={receiveFor ?? undefined}
        onClose={() => setReceiveFor(null)}
        onDone={load}
      />
    </div>
  );
}
