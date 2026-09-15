"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { AdminOrderListItem, AdminOrderListResponse, fetchAdminOrders, OrdersApiError } from "@/lib/orders";
import { formatDateTime, formatMoney } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { Pagination } from "@/components/Pagination";
import { StatusBadge } from "@/components/StatusBadge";

const ORDER_STATUSES = ["PENDING", "CONFIRMED", "COMPLETED", "CANCELLED", "EXPIRED"];
const PAYMENT_STATUSES = ["PENDING", "PROCESSING", "PAID", "FAILED", "CANCELLED", "EXPIRED"];
const FULFILLMENT_STATUSES = [
  "PENDING",
  "PICKING",
  "PACKED",
  "READY_FOR_DELIVERY",
  "ASSIGNED",
  "OUT_FOR_DELIVERY",
  "DELIVERED",
];

const PAGE_SIZE = 20;

export default function OrdersPage() {
  const { getAccessToken } = useAuth();
  const router = useRouter();

  const [data, setData] = useState<AdminOrderListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [paymentStatus, setPaymentStatus] = useState("");
  const [fulfillmentStatus, setFulfillmentStatus] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const hasFilters = Boolean(q || status || paymentStatus || fulfillmentStatus || dateFrom || dateTo);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAdminOrders(token, {
        page,
        page_size: PAGE_SIZE,
        q: q || undefined,
        status: status || undefined,
        payment_status: paymentStatus || undefined,
        fulfillment_status: fulfillmentStatus || undefined,
        date_from: dateFrom ? new Date(dateFrom).toISOString() : undefined,
        date_to: dateTo ? new Date(dateTo).toISOString() : undefined,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof OrdersApiError ? err.message : "Unable to load orders.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, q, status, paymentStatus, fulfillmentStatus, dateFrom, dateTo]);

  useEffect(() => {
    load();
  }, [load]);

  const clearFilters = () => {
    setQ("");
    setStatus("");
    setPaymentStatus("");
    setFulfillmentStatus("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  };

  return (
    <div>
      <PageHeader
        eyebrow="Operations"
        title="Orders"
        description="Search, filter, and manage every order across the marketplace."
      />

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded border border-neutral-200 bg-white p-3">
        <input
          value={q}
          onChange={(e) => {
            setPage(1);
            setQ(e.target.value);
          }}
          placeholder="Order number, customer name, email, or phone"
          className="min-w-[240px] flex-1 rounded border border-neutral-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
        <FilterSelect label="Status" value={status} options={ORDER_STATUSES} onChange={(v) => { setPage(1); setStatus(v); }} />
        <FilterSelect label="Payment" value={paymentStatus} options={PAYMENT_STATUSES} onChange={(v) => { setPage(1); setPaymentStatus(v); }} />
        <FilterSelect label="Delivery" value={fulfillmentStatus} options={FULFILLMENT_STATUSES} onChange={(v) => { setPage(1); setFulfillmentStatus(v); }} />
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => { setPage(1); setDateFrom(e.target.value); }}
          className="rounded border border-neutral-300 px-2 py-1.5 text-sm"
        />
        <span className="text-neutral-400">to</span>
        <input
          type="date"
          value={dateTo}
          onChange={(e) => { setPage(1); setDateTo(e.target.value); }}
          className="rounded border border-neutral-300 px-2 py-1.5 text-sm"
        />
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
            icon="package"
            title="No orders found"
            message={
              hasFilters
                ? "No orders match the current search/filters."
                : "There are genuinely no orders in the system yet."
            }
            action={
              hasFilters ? (
                <button onClick={clearFilters} className="text-sm font-semibold text-primary-700 hover:underline">
                  Clear filters
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
                    <th className="px-4 py-2 font-medium">Order</th>
                    <th className="px-4 py-2 font-medium">Customer</th>
                    <th className="px-4 py-2 font-medium">Items</th>
                    <th className="px-4 py-2 font-medium">Amount</th>
                    <th className="px-4 py-2 font-medium">Payment</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Delivery</th>
                    <th className="px-4 py-2 font-medium">Placed</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {data.items.map((order) => (
                    <OrderRow key={order.id} order={order} onClick={() => router.push(`/orders/${order.id}`)} />
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

function OrderRow({ order, onClick }: { order: AdminOrderListItem; onClick: () => void }) {
  return (
    <tr onClick={onClick} className="cursor-pointer hover:bg-neutral-50">
      <td className="px-4 py-3 font-medium text-primary-900">{order.order_number}</td>
      <td className="px-4 py-3">
        <p className="text-neutral-800">{order.customer_name}</p>
        <p className="text-xs text-neutral-500">{order.customer_email}</p>
      </td>
      <td className="px-4 py-3 text-neutral-600">{order.item_count}</td>
      <td className="px-4 py-3">
        <p className="font-medium text-neutral-800">{formatMoney(order.total_amount, order.currency)}</p>
        {order.applied_promo_code && (
          <p className="mt-0.5 font-mono text-xs text-secondary-700">
            {order.applied_promo_code} (-{formatMoney(order.discount_amount, order.currency)})
          </p>
        )}
      </td>
      <td className="px-4 py-3">
        {order.payment_status ? (
          <div>
            <StatusBadge status={order.payment_status} />
            <p className="mt-0.5 text-xs text-neutral-500">{order.payment_method}</p>
          </div>
        ) : (
          <span className="text-neutral-400">—</span>
        )}
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={order.status} />
      </td>
      <td className="px-4 py-3">
        {order.fulfillment_status ? <StatusBadge status={order.fulfillment_status} /> : <span className="text-neutral-400">—</span>}
      </td>
      <td className="px-4 py-3 text-neutral-500">{formatDateTime(order.placed_at)}</td>
    </tr>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-700"
    >
      <option value="">{label}: All</option>
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt.replaceAll("_", " ")}
        </option>
      ))}
    </select>
  );
}
