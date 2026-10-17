"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import { useOrderEvents } from "@/lib/realtime-context";
import {
  FulfillmentApiError,
  FulfillmentList,
  FulfillmentOrder,
  FulfillmentRow,
  fetchFulfillmentOrder,
  fetchFulfillments,
} from "@/lib/fulfillment";
import { formatDateTime, formatMoney, formatPaymentMethod } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { Pagination } from "@/components/Pagination";
import { StatusBadge } from "@/components/StatusBadge";
import { FulfillmentActions } from "@/components/FulfillmentActions";

const PAGE_SIZE = 20;
const STAGES = [
  { value: "", label: "All" },
  { value: "PENDING", label: "To pick" },
  { value: "PICKING", label: "Picking" },
  { value: "PACKED", label: "Packed" },
  { value: "READY_FOR_DELIVERY", label: "Ready to assign" },
  { value: "ASSIGNED", label: "Assigned" },
  { value: "OUT_FOR_DELIVERY", label: "Out for delivery" },
  { value: "DELIVERED", label: "Delivered" },
];

/** The delivery queue: every fulfilment with its next action. A delivery
 * partner only receives their own assignments (the backend scopes the list). */
export default function DeliveryPage() {
  const { getAccessToken, user } = useAuth();
  const canOpenOrder = !!user && hasPermission(user.roles, "orders.read");

  const [stage, setStage] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<FulfillmentList | null>(null);
  const [orders, setOrders] = useState<Record<number, FulfillmentOrder>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  const load = useCallback(
    async (opts?: { silent?: boolean }) => {
      const token = getAccessToken();
      if (!token) return;
      if (!opts?.silent) setLoading(true);
      setError(null);
      try {
        const result = await fetchFulfillments(token, { status: stage || undefined, page, page_size: PAGE_SIZE });
        setData(result);
        // The list only carries ids; fetch what staff need to recognise each
        // delivery (order number, customer, amount) in parallel, best effort.
        const details = await Promise.all(
          result.items.map((f) => fetchFulfillmentOrder(token, f.id).catch(() => null)),
        );
        setOrders((prev) => {
          const next = { ...prev };
          details.forEach((d) => {
            if (d) next[d.fulfillment_id] = d;
          });
          return next;
        });
      } catch (err) {
        setError(err instanceof FulfillmentApiError ? err.message : "Unable to load deliveries.");
      } finally {
        if (!opts?.silent) setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [stage, page],
  );

  useEffect(() => {
    load();
  }, [load]);
  useOrderEvents(
    useCallback(() => {
      load({ silent: true });
    }, [load]),
  );

  return (
    <div>
      <PageHeader
        eyebrow="Operations"
        title="Delivery"
        description="Pick, pack, assign and deliver. Open a row to see what to pack, where it goes and the next action."
      />

      <div className="mb-4 flex flex-wrap gap-2" role="tablist" aria-label="Delivery stage">
        {STAGES.map((s) => (
          <button
            key={s.value}
            role="tab"
            aria-selected={stage === s.value}
            onClick={() => {
              setStage(s.value);
              setPage(1);
              setOpenId(null);
            }}
            className={`rounded-full border px-3 py-1.5 text-sm font-medium ${
              stage === s.value
                ? "border-primary-700 bg-primary-700 text-white"
                : "border-neutral-300 bg-white text-neutral-700 hover:border-primary-400"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded border border-neutral-200 bg-white">
        {loading ? (
          <TableSkeleton rows={6} columns={5} />
        ) : error ? (
          <ErrorState message={error} onRetry={() => load()} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon="truck"
            title="Nothing in this stage"
            message={stage ? "No deliveries are at this stage right now." : "There are no deliveries yet."}
          />
        ) : (
          <>
            <ul className="divide-y divide-neutral-100">
              {data.items.map((f) => (
                <DeliveryRow
                  key={f.id}
                  fulfillment={f}
                  detail={orders[f.id]}
                  open={openId === f.id}
                  onToggle={() => setOpenId(openId === f.id ? null : f.id)}
                  canOpenOrder={canOpenOrder}
                  onChanged={() => load({ silent: true })}
                />
              ))}
            </ul>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}

function DeliveryRow({
  fulfillment,
  detail,
  open,
  onToggle,
  canOpenOrder,
  onChanged,
}: {
  fulfillment: FulfillmentRow;
  detail: FulfillmentOrder | undefined;
  open: boolean;
  onToggle: () => void;
  canOpenOrder: boolean;
  onChanged: () => void;
}) {
  return (
    <li>
      <button
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3 text-left hover:bg-neutral-50"
      >
        <div className="min-w-0">
          <p className="font-medium text-primary-900">{detail ? detail.order_number : `Order #${fulfillment.order_id}`}</p>
          <p className="truncate text-xs text-neutral-500">
            {detail ? `${detail.customer_name} · ${formatMoney(detail.total_amount, detail.currency)} · ${formatPaymentMethod(detail.payment_method)}` : "Loading details..."}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-neutral-500">Updated {formatDateTime(fulfillment.updated_at)}</span>
          <StatusBadge status={fulfillment.status} />
        </div>
      </button>
      {open && (
        <div className="border-t border-neutral-100 bg-neutral-50 px-4 py-4">
          {!detail ? (
            <p className="text-sm text-neutral-500">Order details are not available for this delivery.</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <p className="eyebrow mb-1">Items</p>
                <ul className="space-y-0.5 text-sm text-neutral-800">
                  {detail.items.map((i) => (
                    <li key={i.id}>
                      {Number(i.quantity)} × {i.product_name} <span className="text-neutral-500">({i.variant_name})</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="eyebrow mb-1">Deliver to</p>
                {detail.address ? (
                  <address className="text-sm not-italic text-neutral-800">
                    {detail.customer_name}
                    <br />
                    {detail.address.address_line_1}
                    {detail.address.address_line_2 ? `, ${detail.address.address_line_2}` : ""}
                    <br />
                    {detail.address.city}, {detail.address.state} {detail.address.postal_code}
                  </address>
                ) : (
                  <p className="text-sm text-neutral-500">No address on this order.</p>
                )}
                {detail.payment_method === "COD" && (
                  <p className="mt-2 text-sm font-semibold text-status-warning">
                    Collect {formatMoney(detail.total_amount, detail.currency)} in cash
                  </p>
                )}
              </div>
            </div>
          )}
          <FulfillmentActions
            fulfillment={fulfillment}
            isCashOnDelivery={detail?.payment_method === "COD"}
            onChanged={onChanged}
          />
          {canOpenOrder && (
            <Link href={`/orders/${fulfillment.order_id}`} className="mt-3 inline-block text-sm font-semibold text-primary-700 hover:underline">
              Open full order →
            </Link>
          )}
        </div>
      )}
    </li>
  );
}
