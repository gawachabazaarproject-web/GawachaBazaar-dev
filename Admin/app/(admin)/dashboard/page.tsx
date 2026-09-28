"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import { useOrderEvents } from "@/lib/realtime-context";
import { DashboardApiError, DashboardSummary, fetchDashboard } from "@/lib/dashboard";
import { formatDateTime, formatMoney } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";

/**
 * "What is happening in Gawacha Bazaar right now?" Every number comes from
 * GET /dashboard (backend app/services/dashboard.py), computed live - this
 * page never shows a figure the backend didn't compute. It refreshes on
 * every realtime order/payment/fulfilment event.
 */
export default function DashboardPage() {
  const { getAccessToken, user } = useAuth();
  const canView = !!user && hasPermission(user.roles, "reports.read");
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token || !canView) return;
    try {
      setData(await fetchDashboard(token));
      setError(null);
    } catch (err) {
      setError(err instanceof DashboardApiError ? err.message : "Unable to load the dashboard.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canView]);

  useEffect(() => {
    load();
  }, [load]);

  // Any order/payment/fulfilment change can move a number here.
  useOrderEvents(() => {
    load();
  });

  const header = (
    <PageHeader
      eyebrow="Overview"
      title="Today at Gawacha Bazaar"
      description="A live snapshot of orders, collections, inventory, and deliveries needing attention."
    />
  );

  if (user && !canView) {
    return (
      <div>
        {header}
        <EmptyState
          icon="grid"
          title="Use the menu to get started"
          message="The business overview is available to Admin and Operations roles. Your tools are in the sidebar."
        />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div>
        {header}
        <ErrorState message={error} onRetry={load} />
      </div>
    );
  }

  const tiles = data?.tiles;
  const tileItems: { label: string; value: string | number | undefined; href?: string }[] = [
    { label: "Orders today", value: tiles?.orders_today, href: "/orders" },
    { label: "Collected today", value: tiles ? formatMoney(tiles.collected_today, tiles.currency) : undefined, href: "/payments" },
    { label: "To fulfil", value: tiles?.to_fulfil, href: "/delivery" },
    { label: "Out for delivery", value: tiles?.out_for_delivery, href: "/delivery" },
    { label: "Delivered today", value: tiles?.delivered_today, href: "/delivery" },
    { label: "Cancelled today", value: tiles?.cancelled_today, href: "/orders" },
  ];

  return (
    <div>
      {header}

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {tileItems.map((tile) => (
          <Link
            key={tile.label}
            href={tile.href ?? "#"}
            className="rounded border border-neutral-200 bg-white p-4 transition-colors hover:border-primary-300"
          >
            <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">{tile.label}</p>
            <p className={`mt-2 font-display text-2xl ${tile.value === undefined ? "text-neutral-300" : "text-primary-900"}`}>
              {tile.value ?? "—"}
            </p>
          </Link>
        ))}
      </div>

      {data && data.refunds_pending_approval > 0 && (
        <Link
          href="/payments"
          className="mb-4 flex items-center justify-between rounded border border-status-warning/40 bg-status-warningLight px-4 py-3 text-sm"
        >
          <span className="font-semibold text-neutral-800">
            {data.refunds_pending_approval} refund{data.refunds_pending_approval === 1 ? "" : "s"} waiting for approval
          </span>
          <span className="font-semibold text-primary-700">Review →</span>
        </Link>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Orders requiring attention" empty="Every confirmed order is being picked." loading={!data}>
          {data?.attention.map((a) => (
            <Link key={a.order_id} href={`/orders/${a.order_id}`} className="flex items-center justify-between py-2.5 text-sm hover:bg-neutral-50">
              <div>
                <p className="font-medium text-primary-900">{a.order_number}</p>
                <p className="text-xs text-neutral-500">
                  {a.reason} · since {formatDateTime(a.since)}
                </p>
              </div>
              <span className="text-neutral-700">{formatMoney(a.total_amount)}</span>
            </Link>
          ))}
        </Panel>

        <Panel
          title={data && data.low_stock_count > data.low_stock.length ? `Low stock (${data.low_stock_count})` : "Low stock"}
          empty="Nothing is running low."
          loading={!data}
          footer={<Link href="/inventory" className="text-xs font-semibold text-primary-700 hover:underline">Open inventory →</Link>}
        >
          {data?.low_stock.map((item) => (
            <div key={item.variant_id} className="flex items-center justify-between py-2.5 text-sm">
              <div>
                <p className="font-medium text-primary-900">{item.product_name}</p>
                <p className="text-xs text-neutral-500">{item.variant_name}</p>
              </div>
              <span className={Number(item.available) <= 0 ? "font-semibold text-status-danger" : "text-status-warning"}>
                {Number(item.available) <= 0 ? "Out of stock" : `${Number(item.available)} ${item.unit} left`}
              </span>
            </div>
          ))}
        </Panel>

        <Panel title="Delivery issues" empty="No delivery is running late." loading={!data}>
          {data?.delivery_issues.map((d) => (
            <Link key={d.fulfillment_id} href={`/orders/${d.order_id}`} className="flex items-center justify-between py-2.5 text-sm hover:bg-neutral-50">
              <div>
                <p className="font-medium text-primary-900">{d.order_number}</p>
                <p className="text-xs text-neutral-500">
                  {d.status === "ASSIGNED" ? "Assigned but not dispatched" : "Out for delivery"} since {formatDateTime(d.since)}
                </p>
              </div>
              <span className="text-xs text-neutral-600">{d.delivery_partner_name ?? "Unassigned"}</span>
            </Link>
          ))}
        </Panel>

        <EmptyState
          icon="star"
          title="Pending reviews"
          message="Product reviews aren't part of the platform yet, so there is nothing to moderate."
        />
      </div>

      {data && (
        <p className="mt-4 text-xs text-neutral-400">
          Today = since {formatDateTime(data.day_start)} (IST). Updated {formatDateTime(data.generated_at)}; refreshes live on order changes.
        </p>
      )}
    </div>
  );
}

function Panel({
  title,
  empty,
  loading,
  footer,
  children,
}: {
  title: string;
  empty: string;
  loading: boolean;
  footer?: React.ReactNode;
  children?: React.ReactNode;
}) {
  const items = React.Children.toArray(children);
  return (
    <div className="rounded border border-neutral-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="font-display text-base font-semibold text-primary-900">{title}</h2>
        {footer}
      </div>
      {loading ? (
        <p className="py-6 text-center text-sm text-neutral-400">Loading…</p>
      ) : items.length === 0 ? (
        <p className="py-6 text-center text-sm text-neutral-500">{empty}</p>
      ) : (
        <div className="divide-y divide-neutral-100">{items}</div>
      )}
    </div>
  );
}
