"use client";

import React, { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  AdminOrderDetail,
  cancelAdminOrder,
  fetchAdminOrderDetail,
  isOrderCancellable,
  OrdersApiError,
} from "@/lib/orders";
import { formatDateTime, formatMoney } from "@/lib/format";
import { ErrorState } from "@/components/ErrorState";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Icon } from "@/components/icons";

export default function OrderDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const orderId = Number(id);
  const { getAccessToken, user } = useAuth();
  const router = useRouter();

  const [order, setOrder] = useState<AdminOrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setOrder(await fetchAdminOrderDetail(token, orderId));
    } catch (err) {
      setError(err instanceof OrdersApiError ? err.message : "Unable to load this order.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCancel = async (reason: string) => {
    const token = getAccessToken();
    if (!token) return;
    setCancelling(true);
    setCancelError(null);
    try {
      const updated = await cancelAdminOrder(token, orderId, reason);
      setOrder(updated);
      setCancelOpen(false);
    } catch (err) {
      // The backend, not this form, decides whether the transition is
      // legal - a conflict here means someone/something already moved
      // this order past the point where cancellation is allowed.
      setCancelError(err instanceof OrdersApiError ? err.message : "Unable to cancel this order.");
    } finally {
      setCancelling(false);
    }
  };

  if (loading) {
    return <div className="animate-pulse text-sm text-neutral-400">Loading order...</div>;
  }
  if (error || !order) {
    return <ErrorState message={error ?? "Order not found."} onRetry={load} />;
  }

  const canCancel = user && hasPermission(user.roles, "orders.cancel") && isOrderCancellable(order.status);

  return (
    <div className="mx-auto max-w-4xl">
      <button onClick={() => router.push("/orders")} className="mb-4 flex items-center gap-1 text-sm text-neutral-500 hover:text-primary-800">
        <Icon name="chevron-left" size={14} /> Back to orders
      </button>

      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-primary-900">{order.order_number}</h1>
          <p className="mt-1 text-sm text-neutral-500">Placed {formatDateTime(order.placed_at)}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={order.status} />
          {canCancel && (
            <button
              onClick={() => setCancelOpen(true)}
              className="rounded border border-status-danger/40 px-3 py-1.5 text-sm font-semibold text-status-danger hover:bg-status-dangerLight"
            >
              Cancel order
            </button>
          )}
        </div>
      </div>

      <Section title="Customer">
        <Row label="Name" value={order.customer_name} />
        <Row label="Email" value={order.customer_email} />
        <Row label="Phone" value={order.customer_phone} />
      </Section>

      {order.address && (
        <Section title="Delivery address">
          <p className="text-sm text-neutral-800">
            {order.address.address_line_1}
            {order.address.address_line_2 ? `, ${order.address.address_line_2}` : ""}
          </p>
          <p className="text-sm text-neutral-500">
            {order.address.city}, {order.address.state} {order.address.postal_code}
          </p>
        </Section>
      )}

      <Section title={`Items (${order.items.length})`}>
        <div className="divide-y divide-neutral-100">
          {order.items.map((item) => (
            <div key={item.id} className="flex items-center justify-between py-2 text-sm">
              <div>
                <p className="font-medium text-neutral-800">{item.product_name}</p>
                <p className="text-xs text-neutral-500">
                  {item.variant_name} · {item.quantity} {item.unit} × {formatMoney(item.unit_price, order.currency)}
                </p>
              </div>
              <p className="font-medium text-neutral-800">{formatMoney(item.total_price, order.currency)}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 space-y-1.5 border-t border-neutral-200 pt-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-neutral-500">Subtotal</span>
            <span className="text-neutral-700">{formatMoney(order.subtotal_amount, order.currency)}</span>
          </div>
          {Number(order.discount_amount) > 0 && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-neutral-500">
                Discount{order.applied_promo_code && ` (${order.applied_promo_code})`}
              </span>
              <span className="text-status-success">-{formatMoney(order.discount_amount, order.currency)}</span>
            </div>
          )}
          <div className="flex items-center justify-between pt-1.5">
            <p className="font-display text-base font-semibold text-primary-900">Total</p>
            <p className="font-display text-base font-semibold text-primary-900">
              {formatMoney(order.total_amount, order.currency)}
            </p>
          </div>
        </div>
        <p className="mt-2 text-xs text-neutral-400">
          There is no separate tax/delivery-fee line in the data model - delivery is always free and no tax is
          charged, so subtotal minus discount is the complete total.
        </p>
      </Section>

      {order.payment && (
        <Section title="Payment">
          <Row label="Method" value={order.payment.payment_method === "COD" ? "Cash on Delivery" : order.payment.payment_method} />
          <div className="flex items-center justify-between py-1.5 text-sm">
            <span className="text-neutral-500">Status</span>
            <StatusBadge status={order.payment.status} />
          </div>
          <Row label="Amount" value={formatMoney(order.payment.amount, order.payment.currency)} />
          {order.payment.paid_at && <Row label="Paid at" value={formatDateTime(order.payment.paid_at)} />}
        </Section>
      )}

      {order.fulfillment && (
        <Section title="Fulfillment">
          <div className="flex items-center justify-between py-1.5 text-sm">
            <span className="text-neutral-500">Status</span>
            <StatusBadge status={order.fulfillment.status} />
          </div>
          <Row
            label="Delivery partner"
            value={order.fulfillment.delivery_partner_user_id ? `User #${order.fulfillment.delivery_partner_user_id}` : "Not yet assigned"}
          />
          {order.fulfillment.delivered_at && <Row label="Delivered at" value={formatDateTime(order.fulfillment.delivered_at)} />}
        </Section>
      )}

      {order.refund && (
        <Section title="Refund">
          <div className="flex items-center justify-between py-1.5 text-sm">
            <span className="text-neutral-500">Status</span>
            <StatusBadge status={order.refund.status} />
          </div>
          <Row label="Amount" value={formatMoney(order.refund.amount, order.refund.currency)} />
          <Row label="Requested at" value={formatDateTime(order.refund.requested_at)} />
          {order.refund.rejection_reason && <Row label="Rejection reason" value={order.refund.rejection_reason} />}
        </Section>
      )}

      <Section title="Timeline">
        <Timeline order={order} />
      </Section>

      <ConfirmDialog
        open={cancelOpen}
        title="Cancel this order?"
        description={`This cancels order ${order.order_number} for the customer. This can't be undone.`}
        confirmLabel="Cancel order"
        danger
        requireReason
        loading={cancelling}
        error={cancelError}
        onConfirm={handleCancel}
        onCancel={() => {
          setCancelOpen(false);
          setCancelError(null);
        }}
      />
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4 rounded border border-neutral-200 bg-white p-4">
      <h2 className="mb-2 font-display text-base font-semibold text-primary-900">{title}</h2>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="text-neutral-500">{label}</span>
      <span className="font-medium text-neutral-800">{value}</span>
    </div>
  );
}

/**
 * Honest, not fabricated: the backend does not persist a full order
 * status-history table (only the current `status`, plus the three
 * cancellation-audit columns - see the Phase 1 audit). This renders
 * exactly what IS real - order placed, then either the current status or,
 * if cancelled, the cancellation record - rather than inventing
 * intermediate "confirmed at", "packed at" timestamps that were never
 * captured anywhere. Building a genuine step-by-step history is a
 * separate backend task (a status-history table written on every
 * transition), not something the frontend can conjure from data that
 * doesn't exist.
 */
function Timeline({ order }: { order: AdminOrderDetail }) {
  const steps: { label: string; timestamp: string; tone: "success" | "danger" | "neutral" }[] = [
    { label: "Order placed", timestamp: order.placed_at, tone: "neutral" },
  ];
  if (order.status === "CANCELLED" && order.cancelled_at) {
    steps.push({ label: "Cancelled", timestamp: order.cancelled_at, tone: "danger" });
  } else {
    steps.push({ label: `Currently ${order.status}`, timestamp: order.placed_at, tone: "success" });
  }

  return (
    <div>
      <div className="space-y-3">
        {steps.map((step, i) => (
          <div key={i} className="flex items-start gap-3">
            <div
              className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                step.tone === "danger" ? "bg-status-danger" : step.tone === "success" ? "bg-status-success" : "bg-neutral-300"
              }`}
            />
            <div>
              <p className="text-sm font-medium text-neutral-800">{step.label}</p>
              <p className="text-xs text-neutral-500">{formatDateTime(step.timestamp)}</p>
            </div>
          </div>
        ))}
      </div>
      {order.cancellation_reason && (
        <p className="mt-3 rounded bg-neutral-50 px-3 py-2 text-xs text-neutral-600">
          Reason: {order.cancellation_reason}
        </p>
      )}
      <p className="mt-3 text-xs text-neutral-400">
        The backend doesn&apos;t persist a step-by-step status history yet (no CONFIRMED-at/PACKED-at timestamps
        exist to show) - this is every timestamp that&apos;s actually recorded for this order.
      </p>
    </div>
  );
}
