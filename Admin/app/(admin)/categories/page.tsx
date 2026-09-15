"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  AdminCategoryListItem,
  CategoryApiError,
  CATEGORY_STATUSES,
  fetchAdminCategories,
} from "@/lib/categories";
import { formatDate } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { StatusBadge } from "@/components/StatusBadge";

// Categories are a small list by nature (a grocery catalog has dozens, not
// thousands) - fetching one full page lets the hierarchy render correctly
// (parents grouped with their children) instead of breaking mid-tree
// across pagination boundaries, which would be a worse admin experience
// for a list this size. If the category count ever genuinely grows large
// enough for this to matter, that's a real backend-pagination problem to
// solve then, not something to fake now.
const PAGE_SIZE = 100;

interface TreeRow extends AdminCategoryListItem {
  depth: number;
}

function buildTree(items: AdminCategoryListItem[]): TreeRow[] {
  const byParent = new Map<number | null, AdminCategoryListItem[]>();
  for (const item of items) {
    const key = item.parent_id;
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key)!.push(item);
  }
  const result: TreeRow[] = [];
  const visit = (parentId: number | null, depth: number) => {
    for (const item of byParent.get(parentId) ?? []) {
      result.push({ ...item, depth });
      visit(item.id, depth + 1);
    }
  };
  visit(null, 0);
  // Orphans (parent not in the current filtered set, e.g. parent on a
  // different status) still need to show up somewhere rather than vanish.
  const includedIds = new Set(result.map((r) => r.id));
  for (const item of items) {
    if (!includedIds.has(item.id)) result.push({ ...item, depth: 0 });
  }
  return result;
}

export default function CategoriesPage() {
  const { getAccessToken } = useAuth();
  const router = useRouter();

  const [items, setItems] = useState<AdminCategoryListItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const hasFilters = Boolean(q || status);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAdminCategories(token, {
        page: 1,
        page_size: PAGE_SIZE,
        q: q || undefined,
        status: status || undefined,
      });
      setItems(result.items);
    } catch (err) {
      setError(err instanceof CategoryApiError ? err.message : "Unable to load categories.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, status]);

  useEffect(() => {
    load();
  }, [load]);

  const rows = useMemo(() => (items ? buildTree(items) : []), [items]);

  const clearFilters = () => {
    setQ("");
    setStatus("");
  };

  return (
    <div>
      <PageHeader
        eyebrow="Catalog"
        title="Categories"
        description="Organize and control how customers discover products across Gawacha Bazaar."
        actions={
          <button
            onClick={() => router.push("/categories/new")}
            className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700"
          >
            Create category
          </button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded border border-neutral-200 bg-white p-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Category name or slug"
          className="min-w-[220px] flex-1 rounded border border-neutral-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-700"
        >
          <option value="">Status: All</option>
          {CATEGORY_STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        {hasFilters && (
          <button onClick={clearFilters} className="text-sm font-medium text-primary-700 hover:underline">
            Clear filters
          </button>
        )}
      </div>

      <div className="overflow-hidden rounded border border-neutral-200 bg-white">
        {loading ? (
          <TableSkeleton rows={6} columns={6} />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : rows.length === 0 ? (
          <EmptyState
            icon="box"
            title={hasFilters ? "No categories match" : "No categories yet"}
            message={hasFilters ? "Try a different search or clear filters." : "Create your first category to get started."}
            action={
              hasFilters ? (
                <button onClick={clearFilters} className="text-sm font-semibold text-primary-700 hover:underline">
                  Clear filters
                </button>
              ) : (
                <button onClick={() => router.push("/categories/new")} className="text-sm font-semibold text-primary-700 hover:underline">
                  Create category →
                </button>
              )
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Category</th>
                  <th className="px-4 py-2 font-medium">Slug</th>
                  <th className="px-4 py-2 font-medium">Products</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {rows.map((row) => (
                  <tr
                    key={row.id}
                    onClick={() => router.push(`/categories/${row.id}`)}
                    className="cursor-pointer hover:bg-neutral-50"
                  >
                    <td className="px-4 py-3">
                      <span style={{ paddingLeft: row.depth * 20 }} className="inline-flex items-center gap-1.5">
                        {row.depth > 0 && <span className="text-neutral-300">└</span>}
                        <span className="font-medium text-primary-900">{row.name}</span>
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-neutral-500">{row.slug}</td>
                    <td className="px-4 py-3 text-neutral-600">{row.product_count}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-neutral-500">{formatDate(row.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
