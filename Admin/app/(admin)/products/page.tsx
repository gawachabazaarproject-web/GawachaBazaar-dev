"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { readInitialQuery, useDebounced, useUrlQuerySync } from "@/lib/use-list-query";
import { hasPermission } from "@/lib/permissions";
import {
  AdminProductListItem,
  AdminProductListResponse,
  Category,
  CatalogApiError,
  deleteProduct,
  fetchAdminProducts,
  fetchCategories,
  PRODUCT_STATUSES,
} from "@/lib/products";
import { formatDate, formatMoney } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { Pagination } from "@/components/Pagination";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfirmDialog } from "@/components/ConfirmDialog";

const PAGE_SIZE = 20;
const LOW_STOCK_THRESHOLD = 10;

export default function ProductsPage() {
  const { getAccessToken, user } = useAuth();
  const router = useRouter();
  const canDelete = user && hasPermission(user.roles, "products.delete");
  const [toDelete, setToDelete] = useState<AdminProductListItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [data, setData] = useState<AdminProductListResponse | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [q, setQ] = useState(readInitialQuery);
  const dq = useDebounced(q);
  useUrlQuerySync((v) => { setPage(1); setQ(v); });
  const [status, setStatus] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");

  const hasFilters = Boolean(q || status || categoryId || priceMin || priceMax);

  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => undefined);
  }, []);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAdminProducts(token, {
        page,
        page_size: PAGE_SIZE,
        q: dq || undefined,
        status: status || undefined,
        category_id: categoryId ? Number(categoryId) : undefined,
        price_min: priceMin || undefined,
        price_max: priceMax || undefined,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to load products.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, dq, status, categoryId, priceMin, priceMax]);

  useEffect(() => {
    load();
  }, [load]);

  const handleDelete = async () => {
    const token = getAccessToken();
    if (!token || !toDelete) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteProduct(token, toDelete.id);
      setToDelete(null);
      await load();
    } catch (err) {
      setDeleteError(err instanceof CatalogApiError ? err.message : "Unable to delete this product.");
    } finally {
      setDeleting(false);
    }
  };

  const clearFilters = () => {
    setQ("");
    setStatus("");
    setCategoryId("");
    setPriceMin("");
    setPriceMax("");
    setPage(1);
  };

  return (
    <div>
      <PageHeader
        eyebrow="Catalog"
        title="Products"
        description="Manage the products available across Gawacha Bazaar."
        actions={
          <button
            onClick={() => router.push("/products/new")}
            className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700"
          >
            Create product
          </button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded border border-neutral-200 bg-white p-3">
        <input
          value={q}
          onChange={(e) => { setPage(1); setQ(e.target.value); }}
          placeholder="Product name or slug"
          className="min-w-[220px] flex-1 rounded border border-neutral-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
        <select
          value={status}
          onChange={(e) => { setPage(1); setStatus(e.target.value); }}
          className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-700"
        >
          <option value="">Status: All</option>
          {PRODUCT_STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={categoryId}
          onChange={(e) => { setPage(1); setCategoryId(e.target.value); }}
          className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-700"
        >
          <option value="">Category: All</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id} style={{ fontWeight: c.parent_id ? 400 : 700 }}>{c.name}</option>
          ))}
        </select>
        <input
          type="number"
          value={priceMin}
          onChange={(e) => { setPage(1); setPriceMin(e.target.value); }}
          placeholder="Min ₹"
          className="w-20 rounded border border-neutral-300 px-2 py-1.5 text-sm"
        />
        <span className="text-neutral-400">to</span>
        <input
          type="number"
          value={priceMax}
          onChange={(e) => { setPage(1); setPriceMax(e.target.value); }}
          placeholder="Max ₹"
          className="w-20 rounded border border-neutral-300 px-2 py-1.5 text-sm"
        />
        {hasFilters && (
          <button onClick={clearFilters} className="text-sm font-medium text-primary-700 hover:underline">
            Clear filters
          </button>
        )}
      </div>

      <div className="overflow-hidden rounded border border-neutral-200 bg-white">
        {loading ? (
          <TableSkeleton rows={8} columns={8} />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon="tag"
            title={hasFilters ? "No products match these filters" : "No products yet"}
            message={hasFilters ? "Try a different search or clear filters." : "Create your first product to get started."}
            action={
              hasFilters ? (
                <button onClick={clearFilters} className="text-sm font-semibold text-primary-700 hover:underline">
                  Clear filters
                </button>
              ) : (
                <button onClick={() => router.push("/products/new")} className="text-sm font-semibold text-primary-700 hover:underline">
                  Create product →
                </button>
              )
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                  <tr>
                    <th className="px-4 py-2 font-medium">Image</th>
                    <th className="px-4 py-2 font-medium">Product</th>
                    <th className="px-4 py-2 font-medium">Category</th>
                    <th className="px-4 py-2 font-medium">Price</th>
                    <th className="px-4 py-2 font-medium">Stock</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Updated</th>
                    {canDelete && <th className="px-4 py-2" />}
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {data.items.map((product) => (
                    <ProductRow
                      key={product.id}
                      product={product}
                      onClick={() => router.push(`/products/${product.id}`)}
                      onDelete={canDelete ? () => { setDeleteError(null); setToDelete(product); } : undefined}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
          </>
        )}
      </div>

      <ConfirmDialog
        open={toDelete !== null}
        title={`Delete "${toDelete?.name ?? ""}"?`}
        description="This permanently removes the product with its variants, prices, photos and stock records. It can't be undone. Products that already appear in orders can't be deleted - archive those instead."
        confirmLabel="Delete product"
        danger
        loading={deleting}
        error={deleteError}
        onConfirm={handleDelete}
        onCancel={() => setToDelete(null)}
      />
    </div>
  );
}

function ProductRow({ product, onClick, onDelete }: { product: AdminProductListItem; onClick: () => void; onDelete?: () => void }) {
  const stock = Number.parseFloat(product.total_available_stock);
  return (
    <tr onClick={onClick} className="cursor-pointer hover:bg-neutral-50">
      <td className="px-4 py-2">
        <div className="h-11 w-11 overflow-hidden rounded bg-neutral-100">
          {product.primary_image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={product.primary_image_url} alt="" className="h-full w-full object-cover" />
          ) : null}
        </div>
      </td>
      <td className="px-4 py-3">
        <p className="font-medium text-primary-900">{product.name}</p>
        <p className="text-xs text-neutral-500">{product.variant_count} variant{product.variant_count === 1 ? "" : "s"}</p>
      </td>
      <td className="px-4 py-3 text-neutral-600">{product.category_name}</td>
      <td className="px-4 py-3 font-medium text-neutral-800">
        {product.price ? formatMoney(product.price, product.currency ?? "INR") : <span className="text-neutral-400">—</span>}
      </td>
      <td className="px-4 py-3">
        {stock === 0 ? (
          <span className="text-xs font-semibold text-status-danger">Out of stock</span>
        ) : stock < LOW_STOCK_THRESHOLD ? (
          <span className="text-xs font-semibold text-status-warning">Low: {stock}</span>
        ) : (
          <span className="text-neutral-600">{stock}</span>
        )}
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={product.status} />
      </td>
      <td className="px-4 py-3 text-neutral-500">{formatDate(product.updated_at)}</td>
      {onDelete && (
        <td className="px-4 py-3 text-right">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="text-xs font-semibold text-status-danger hover:underline"
          >
            Delete
          </button>
        </td>
      )}
    </tr>
  );
}
