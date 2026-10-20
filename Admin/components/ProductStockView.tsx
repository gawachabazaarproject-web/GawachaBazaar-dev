"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { fetchProductStock, InventoryApiError, packCount, packSize, ProductStockListResponse } from "@/lib/inventory";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Pagination } from "@/components/Pagination";
import { TableSkeleton } from "@/components/TableSkeleton";

const PAGE_SIZE = 20;
const num = (v: string | number) => String(Number(Number(v).toFixed(3)));

/** Inventory by product: the shared stock total ("100 kg") with each size's
 * packs left and weight underneath. */
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
        <div key={p.product_id} className="rounded border border-neutral-200 bg-white">
          <div className="flex items-start justify-between gap-4 border-b border-neutral-100 px-4 py-3">
            <div className="min-w-0">
              <a href={`/products/${p.product_id}`} className="font-medium text-primary-900 hover:underline">{p.product_name}</a>
              <p className="text-xs text-neutral-500">{p.category_name}</p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase tracking-wide text-neutral-500">Total in stock</p>
              <p className="font-display text-xl font-semibold text-primary-900">
                {p.totals.length === 0
                  ? "—"
                  : p.totals.map((t) => `${num(t.amount)} ${t.amount_unit}`).join(" + ")}
              </p>
            </div>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-neutral-400">
              <tr>
                <th className="px-4 py-1.5 font-medium">Size</th>
                <th className="px-4 py-1.5 text-right font-medium">Packs left</th>
                <th className="px-4 py-1.5 text-right font-medium">Weight / amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-50">
              {p.variants.map((v) => (
                <tr key={v.variant_id} onClick={() => router.push(`/products/${p.product_id}`)} className="cursor-pointer hover:bg-neutral-50">
                  <td className="px-4 py-2">
                    <span className="font-medium text-neutral-800">{v.variant_name}</span>
                    <span className="ml-2 text-xs text-neutral-400">{v.sku} · pack of {packSize(v.pack_quantity, v.pack_unit)}</span>
                  </td>
                  <td className={`px-4 py-2 text-right ${Number(v.available_packs) === 0 ? "font-semibold text-status-danger" : "text-neutral-800"}`}>
                    {packCount(v.available_packs)}
                  </td>
                  <td className="px-4 py-2 text-right text-neutral-600">{num(v.available_amount)} {v.amount_unit}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
      <div className="rounded border border-neutral-200 bg-white">
        <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
      </div>
    </div>
  );
}
