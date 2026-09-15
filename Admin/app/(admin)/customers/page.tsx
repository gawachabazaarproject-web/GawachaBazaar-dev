"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  AdminCustomerListItem,
  AdminCustomerListResponse,
  CUSTOMER_ACCOUNT_STATUSES,
  CUSTOMER_ACTIVITY_FILTERS,
  CustomerApiError,
  CustomersDashboard,
  fetchCustomers,
  fetchCustomersDashboard,
} from "@/lib/customers";
import { formatDate, formatMoney } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { Pagination } from "@/components/Pagination";
import { StatusBadge } from "@/components/StatusBadge";

const PAGE_SIZE = 20;

const ACTIVITY_LABELS: Record<string, string> = {
  new: "New (last 30 days)",
  returning: "Returning (2+ completed orders)",
  no_orders: "No orders yet",
  recently_active: "Recently active",
  inactive: "Inactive (no recent order)",
};

type SortField = "created_at" | "name" | "last_order_at" | "order_count" | "total_spend" | "average_order_value";

export default function CustomersPage() {
  const { getAccessToken } = useAuth();
  const router = useRouter();

  const [dashboard, setDashboard] = useState<CustomersDashboard | null>(null);
  const [data, setData] = useState<AdminCustomerListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [accountStatus, setAccountStatus] = useState("");
  const [activity, setActivity] = useState("");
  const [registeredFrom, setRegisteredFrom] = useState("");
  const [registeredTo, setRegisteredTo] = useState("");
  const [lastOrderFrom, setLastOrderFrom] = useState("");
  const [lastOrderTo, setLastOrderTo] = useState("");
  const [showDateFilters, setShowDateFilters] = useState(false);
  const [sortBy, setSortBy] = useState<SortField>("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const hasFilters = Boolean(
    q || accountStatus || activity || registeredFrom || registeredTo || lastOrderFrom || lastOrderTo,
  );

  const loadDashboard = useCallback(() => {
    const token = getAccessToken();
    if (!token) return;
    fetchCustomersDashboard(token).then(setDashboard).catch(() => undefined);
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
      const result = await fetchCustomers(token, {
        page,
        page_size: PAGE_SIZE,
        q: q || undefined,
        account_status: accountStatus || undefined,
        activity: activity || undefined,
        registered_from: registeredFrom ? new Date(registeredFrom).toISOString() : undefined,
        registered_to: registeredTo ? new Date(registeredTo).toISOString() : undefined,
        last_order_from: lastOrderFrom ? new Date(lastOrderFrom).toISOString() : undefined,
        last_order_to: lastOrderTo ? new Date(lastOrderTo).toISOString() : undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof CustomerApiError ? err.message : "Unable to load customers.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, q, accountStatus, activity, registeredFrom, registeredTo, lastOrderFrom, lastOrderTo, sortBy, sortDir]);

  useEffect(() => {
    load();
  }, [load]);

  const clearFilters = () => {
    setPage(1);
    setQ("");
    setAccountStatus("");
    setActivity("");
    setRegisteredFrom("");
    setRegisteredTo("");
    setLastOrderFrom("");
    setLastOrderTo("");
  };

  const toggleSort = (field: SortField) => {
    setPage(1);
    if (sortBy === field) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="People"
        title="Customers"
        description="Search customers, review their orders, and manage account status."
      />

      {dashboard && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          <Metric label="Total" value={dashboard.total_customers} emphasize />
          <Metric label="Active" value={dashboard.active_customers} tone="success" onClick={() => { setPage(1); setAccountStatus("ACTIVE"); }} />
          <Metric label="Inactive" value={dashboard.inactive_customers} tone={dashboard.inactive_customers > 0 ? "warning" : undefined} onClick={() => { setPage(1); setAccountStatus("INACTIVE"); }} />
          <Metric label="Suspended" value={dashboard.suspended_customers} tone={dashboard.suspended_customers > 0 ? "danger" : undefined} onClick={() => { setPage(1); setAccountStatus("SUSPENDED"); }} />
          <Metric label="New (30d)" value={dashboard.new_customers_last_30_days} onClick={() => { setPage(1); setActivity("new"); }} />
          <Metric label="With orders" value={dashboard.customers_with_orders} onClick={() => { setPage(1); setAccountStatus(""); setActivity(""); }} />
          <Metric label="Returning" value={dashboard.returning_customers} onClick={() => { setPage(1); setActivity("returning"); }} />
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded border border-neutral-200 bg-white p-3">
        <input
          value={q}
          onChange={(e) => { setPage(1); setQ(e.target.value); }}
          placeholder="Name, email, phone, or customer ID"
          className="min-w-[240px] flex-1 rounded border border-neutral-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
        <select
          value={accountStatus}
          onChange={(e) => { setPage(1); setAccountStatus(e.target.value); }}
          className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-700"
        >
          <option value="">Status: All</option>
          {CUSTOMER_ACCOUNT_STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={activity}
          onChange={(e) => { setPage(1); setActivity(e.target.value); }}
          className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-700"
        >
          <option value="">Activity: All</option>
          {CUSTOMER_ACTIVITY_FILTERS.map((a) => (
            <option key={a} value={a}>{ACTIVITY_LABELS[a]}</option>
          ))}
        </select>
        <button
          onClick={() => setShowDateFilters((v) => !v)}
          className={`rounded border px-2 py-1.5 text-sm font-medium ${
            showDateFilters || registeredFrom || registeredTo || lastOrderFrom || lastOrderTo
              ? "border-primary-700 text-primary-800"
              : "border-neutral-300 text-neutral-600"
          }`}
        >
          Date filters {showDateFilters ? "▲" : "▼"}
        </button>
        {hasFilters && (
          <button onClick={clearFilters} className="text-sm font-medium text-primary-700 hover:underline">
            Clear filters
          </button>
        )}

        {showDateFilters && (
          <div className="flex w-full flex-wrap items-center gap-3 border-t border-neutral-100 pt-3">
            <DateRangeField
              label="Registered"
              from={registeredFrom}
              to={registeredTo}
              onFromChange={(v) => { setPage(1); setRegisteredFrom(v); }}
              onToChange={(v) => { setPage(1); setRegisteredTo(v); }}
            />
            <DateRangeField
              label="Last order"
              from={lastOrderFrom}
              to={lastOrderTo}
              onFromChange={(v) => { setPage(1); setLastOrderFrom(v); }}
              onToChange={(v) => { setPage(1); setLastOrderTo(v); }}
            />
          </div>
        )}
      </div>

      <div className="overflow-hidden rounded border border-neutral-200 bg-white">
        {loading ? (
          <TableSkeleton rows={8} columns={7} />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon="users"
            title={hasFilters ? "No customers match" : "No customers yet"}
            message={hasFilters ? "Try a different search or clear filters." : "Customers will appear here once people register."}
            action={hasFilters ? <button onClick={clearFilters} className="text-sm font-semibold text-primary-700 hover:underline">Clear filters</button> : undefined}
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                  <tr>
                    <SortableHeader label="Customer" field="name" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} />
                    <th className="px-4 py-2 font-medium">Contact</th>
                    <SortableHeader label="Orders" field="order_count" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} />
                    <SortableHeader label="Total spend" field="total_spend" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} />
                    <SortableHeader label="Avg order" field="average_order_value" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} />
                    <SortableHeader label="Last order" field="last_order_at" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} />
                    <th className="px-4 py-2 font-medium">Status</th>
                    <SortableHeader label="Joined" field="created_at" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} />
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {data.items.map((row) => (
                    <CustomerRow key={row.id} row={row} onClick={() => router.push(`/customers/${row.id}`)} />
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

function DateRangeField({
  label,
  from,
  to,
  onFromChange,
  onToChange,
}: {
  label: string;
  from: string;
  to: string;
  onFromChange: (value: string) => void;
  onToChange: (value: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</span>
      <input
        type="date"
        value={from}
        onChange={(e) => onFromChange(e.target.value)}
        className="rounded border border-neutral-300 px-2 py-1.5 text-sm"
      />
      <span className="text-neutral-400">to</span>
      <input
        type="date"
        value={to}
        onChange={(e) => onToChange(e.target.value)}
        className="rounded border border-neutral-300 px-2 py-1.5 text-sm"
      />
    </div>
  );
}

function SortableHeader({
  label,
  field,
  sortBy,
  sortDir,
  onSort,
}: {
  label: string;
  field: SortField;
  sortBy: SortField;
  sortDir: "asc" | "desc";
  onSort: (field: SortField) => void;
}) {
  const active = sortBy === field;
  return (
    <th className="px-4 py-2 font-medium">
      <button onClick={() => onSort(field)} className={`flex items-center gap-1 ${active ? "text-primary-800" : ""}`}>
        {label}
        {active && <span>{sortDir === "desc" ? "↓" : "↑"}</span>}
      </button>
    </th>
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

function CustomerRow({ row, onClick }: { row: AdminCustomerListItem; onClick: () => void }) {
  return (
    <tr onClick={onClick} className="cursor-pointer hover:bg-neutral-50">
      <td className="px-4 py-3">
        <p className="font-medium text-primary-900">{row.name}</p>
        <p className="text-xs text-neutral-500">#{row.id}</p>
      </td>
      <td className="px-4 py-3 text-neutral-600">
        <p className="truncate max-w-[200px]">{row.email}</p>
        <p className="text-xs text-neutral-400">{row.phone}</p>
      </td>
      <td className="px-4 py-3 text-neutral-600">{row.order_count}</td>
      <td className="px-4 py-3 text-neutral-700">{formatMoney(row.total_spend)}</td>
      <td className="px-4 py-3 text-neutral-600">{row.average_order_value ? formatMoney(row.average_order_value) : "—"}</td>
      <td className="px-4 py-3 text-neutral-500">{row.last_order_at ? formatDate(row.last_order_at) : "Never"}</td>
      <td className="px-4 py-3"><StatusBadge status={row.account_status} /></td>
      <td className="px-4 py-3 text-neutral-500">{formatDate(row.created_at)}</td>
    </tr>
  );
}
