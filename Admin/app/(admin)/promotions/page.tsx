"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  PROMOTION_EFFECTIVE_STATUSES,
  PromotionApiError,
  PromotionListItem,
  PromotionListResponse,
  PromotionsDashboard,
  fetchPromotions,
  fetchPromotionsDashboard,
} from "@/lib/promotions";
import { formatDate, formatMoney } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { Pagination } from "@/components/Pagination";
import { StatusBadge } from "@/components/StatusBadge";

const PAGE_SIZE = 20;

export default function PromotionsPage() {
  const { getAccessToken, user } = useAuth();
  const router = useRouter();

  const [dashboard, setDashboard] = useState<PromotionsDashboard | null>(null);
  const [data, setData] = useState<PromotionListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [effectiveStatus, setEffectiveStatus] = useState("");
  const hasFilters = Boolean(q || effectiveStatus);

  const canCreate = user && hasPermission(user.roles, "promotions.create");

  const loadDashboard = useCallback(() => {
    const token = getAccessToken();
    if (!token) return;
    fetchPromotionsDashboard(token).then(setDashboard).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchPromotions(token, {
        page,
        page_size: PAGE_SIZE,
        q: q || undefined,
        effective_status: effectiveStatus || undefined,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof PromotionApiError ? err.message : "Unable to load promotions.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, q, effectiveStatus]);

  useEffect(() => {
    load();
  }, [load]);

  const clearFilters = () => {
    setPage(1);
    setQ("");
    setEffectiveStatus("");
  };

  return (
    <div>
      <PageHeader
        eyebrow="Marketing"
        title="Promotions"
        description="Coupon codes and automatic discounts - eligibility, discount amount, and usage limits are all enforced by the backend at checkout."
        actions={
          canCreate ? (
            <button
              onClick={() => router.push("/promotions/new")}
              className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700"
            >
              Create promotion
            </button>
          ) : undefined
        }
      />

      {dashboard && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Metric label="Active" value={dashboard.active_count} tone="success" onClick={() => { setPage(1); setEffectiveStatus("ACTIVE"); }} />
          <Metric label="Scheduled" value={dashboard.scheduled_count} onClick={() => { setPage(1); setEffectiveStatus("SCHEDULED"); }} />
          <Metric label="Paused" value={dashboard.paused_count} tone={dashboard.paused_count > 0 ? "warning" : undefined} onClick={() => { setPage(1); setEffectiveStatus("PAUSED"); }} />
          <Metric label="Expired" value={dashboard.expired_count} onClick={() => { setPage(1); setEffectiveStatus("EXPIRED"); }} />
          <Metric label="Redemptions" value={dashboard.total_redemptions} emphasize />
          <Metric label="Discount granted" value={formatMoney(dashboard.total_discount_granted)} emphasize />
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded border border-neutral-200 bg-white p-3">
        <input
          value={q}
          onChange={(e) => { setPage(1); setQ(e.target.value); }}
          placeholder="Promotion name or code"
          className="min-w-[220px] flex-1 rounded border border-neutral-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
        <select
          value={effectiveStatus}
          onChange={(e) => { setPage(1); setEffectiveStatus(e.target.value); }}
          className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-700"
        >
          <option value="">Status: All</option>
          {PROMOTION_EFFECTIVE_STATUSES.map((s) => (
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
          <TableSkeleton rows={6} columns={7} />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon="megaphone"
            title={hasFilters ? "No promotions match" : "No promotions yet"}
            message={hasFilters ? "Try a different search or clear filters." : "Create your first promotion to offer a discount or coupon code."}
            action={
              hasFilters ? (
                <button onClick={clearFilters} className="text-sm font-semibold text-primary-700 hover:underline">
                  Clear filters
                </button>
              ) : canCreate ? (
                <button onClick={() => router.push("/promotions/new")} className="text-sm font-semibold text-primary-700 hover:underline">
                  Create promotion →
                </button>
              ) : undefined
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                  <tr>
                    <th className="px-4 py-2 font-medium">Promotion</th>
                    <th className="px-4 py-2 font-medium">Code</th>
                    <th className="px-4 py-2 font-medium">Discount</th>
                    <th className="px-4 py-2 font-medium">Scope</th>
                    <th className="px-4 py-2 font-medium">Usage</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Ends</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {data.items.map((row) => (
                    <PromotionRow key={row.id} row={row} onClick={() => router.push(`/promotions/${row.id}`)} />
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
          </>
        )}
      </div>
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
  tone?: "warning" | "danger" | "success";
  onClick?: () => void;
}) {
  const toneClass =
    tone === "danger" ? "text-status-danger" : tone === "warning" ? "text-status-warning" : tone === "success" ? "text-status-success" : "text-primary-900";
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

function discountLabel(row: PromotionListItem): string {
  return row.discount_type === "PERCENTAGE" ? `${row.discount_value}% off` : `${formatMoney(row.discount_value)} off`;
}

function PromotionRow({ row, onClick }: { row: PromotionListItem; onClick: () => void }) {
  return (
    <tr onClick={onClick} className="cursor-pointer hover:bg-neutral-50">
      <td className="px-4 py-3">
        <p className="font-medium text-primary-900">{row.name}</p>
        <p className="text-xs text-neutral-500">by {row.created_by_name}</p>
      </td>
      <td className="px-4 py-3 font-mono text-xs text-neutral-600">{row.code ?? "— (automatic)"}</td>
      <td className="px-4 py-3 text-neutral-700">{discountLabel(row)}</td>
      <td className="px-4 py-3 text-neutral-600">{row.customer_scope.replaceAll("_", " ")}</td>
      <td className="px-4 py-3 text-neutral-600">
        {row.redemption_count}
        {row.usage_limit_total !== null ? ` / ${row.usage_limit_total}` : ""}
      </td>
      <td className="px-4 py-3"><StatusBadge status={row.effective_status} /></td>
      <td className="px-4 py-3 text-neutral-500">{row.ends_at ? formatDate(row.ends_at) : "No end date"}</td>
    </tr>
  );
}
