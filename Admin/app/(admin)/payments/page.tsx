"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  AdminPaymentListItem,
  AdminPaymentListResponse,
  AdminRefund,
  AdminRefundListResponse,
  approveRefund,
  fetchAdminPayments,
  fetchAdminRefunds,
  PaymentsApiError,
  processRefund,
  refundActionsFor,
  rejectRefund,
} from "@/lib/payments";
import { formatDateTime, formatMoney } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { Pagination } from "@/components/Pagination";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfirmDialog } from "@/components/ConfirmDialog";

const PAYMENT_STATUSES = ["PENDING", "PROCESSING", "PAID", "FAILED", "CANCELLED", "EXPIRED"];
const PAYMENT_METHODS = ["UPI", "COD"];
const REFUND_STATUSES = ["PENDING_APPROVAL", "APPROVED", "REJECTED", "PROCESSING", "REFUNDED", "FAILED"];
const PAGE_SIZE = 20;

export default function PaymentsPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<"payments" | "refunds">("payments");
  const canManageRefunds = Boolean(user && hasPermission(user.roles, "orders.refund"));

  return (
    <div>
      <PageHeader
        eyebrow="Finance"
        title="Payments & Refunds"
        description="Review payment status across the platform and manage the refund approval workflow."
      />

      <div className="mb-4 flex gap-1 border-b border-neutral-200">
        <TabButton active={tab === "payments"} onClick={() => setTab("payments")}>
          All Payments
        </TabButton>
        <TabButton active={tab === "refunds"} onClick={() => setTab("refunds")}>
          Refund Queue
        </TabButton>
      </div>

      {tab === "payments" ? <PaymentsTab /> : <RefundsTab canManage={canManageRefunds} />}
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`-mb-px border-b-2 px-4 py-2 text-sm font-semibold ${
        active ? "border-primary-700 text-primary-900" : "border-transparent text-neutral-500 hover:text-primary-800"
      }`}
    >
      {children}
    </button>
  );
}

function PaymentsTab() {
  const { getAccessToken } = useAuth();
  const router = useRouter();

  const [data, setData] = useState<AdminPaymentListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [method, setMethod] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const hasFilters = Boolean(q || status || method || dateFrom || dateTo);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAdminPayments(token, {
        page,
        page_size: PAGE_SIZE,
        q: q || undefined,
        status: status || undefined,
        payment_method: method || undefined,
        date_from: dateFrom ? new Date(dateFrom).toISOString() : undefined,
        date_to: dateTo ? new Date(dateTo).toISOString() : undefined,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof PaymentsApiError ? err.message : "Unable to load payments.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, q, status, method, dateFrom, dateTo]);

  useEffect(() => {
    load();
  }, [load]);

  const clearFilters = () => {
    setQ("");
    setStatus("");
    setMethod("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2 rounded border border-neutral-200 bg-white p-3">
        <input
          value={q}
          onChange={(e) => {
            setPage(1);
            setQ(e.target.value);
          }}
          placeholder="Order number, customer name/email, or gateway order id"
          className="min-w-[260px] flex-1 rounded border border-neutral-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
        <FilterSelect label="Status" value={status} options={PAYMENT_STATUSES} onChange={(v) => { setPage(1); setStatus(v); }} />
        <FilterSelect label="Method" value={method} options={PAYMENT_METHODS} onChange={(v) => { setPage(1); setMethod(v); }} />
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
          <TableSkeleton rows={8} columns={7} />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon="credit-card"
            title="No payments found"
            message={hasFilters ? "No payments match the current search/filters." : "There are genuinely no payments in the system yet."}
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
                    <th className="px-4 py-2 font-medium">Method</th>
                    <th className="px-4 py-2 font-medium">Amount</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Gateway ref</th>
                    <th className="px-4 py-2 font-medium">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {data.items.map((payment) => (
                    <PaymentRow key={payment.id} payment={payment} onClick={() => router.push(`/payments/${payment.id}`)} />
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

function PaymentRow({ payment, onClick }: { payment: AdminPaymentListItem; onClick: () => void }) {
  return (
    <tr onClick={onClick} className="cursor-pointer hover:bg-neutral-50">
      <td className="px-4 py-3 font-medium text-primary-900">{payment.order_number}</td>
      <td className="px-4 py-3">
        <p className="text-neutral-800">{payment.customer_name}</p>
        <p className="text-xs text-neutral-500">{payment.customer_email}</p>
      </td>
      <td className="px-4 py-3 text-neutral-600">{payment.payment_method === "COD" ? "Cash on Delivery" : payment.payment_method}</td>
      <td className="px-4 py-3 font-medium text-neutral-800">{formatMoney(payment.amount, payment.currency)}</td>
      <td className="px-4 py-3">
        <StatusBadge status={payment.status} />
      </td>
      <td className="px-4 py-3 font-mono text-xs text-neutral-500">{payment.gateway_order_id ?? "—"}</td>
      <td className="px-4 py-3 text-neutral-500">{formatDateTime(payment.created_at)}</td>
    </tr>
  );
}

function RefundsTab({ canManage }: { canManage: boolean }) {
  const { getAccessToken } = useAuth();
  const router = useRouter();

  const [data, setData] = useState<AdminRefundListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");

  const [rejectTarget, setRejectTarget] = useState<AdminRefund | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actingId, setActingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAdminRefunds(token, { page, page_size: PAGE_SIZE, status: status || undefined });
      setData(result);
    } catch (err) {
      setError(err instanceof PaymentsApiError ? err.message : "Unable to load refunds.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, status]);

  useEffect(() => {
    load();
  }, [load]);

  const handleApprove = async (refund: AdminRefund) => {
    const token = getAccessToken();
    if (!token) return;
    setActingId(refund.id);
    setActionError(null);
    try {
      await approveRefund(token, refund.id);
      await load();
    } catch (err) {
      setActionError(err instanceof PaymentsApiError ? err.message : "Unable to approve this refund.");
    } finally {
      setActingId(null);
    }
  };

  const handleProcess = async (refund: AdminRefund) => {
    const token = getAccessToken();
    if (!token) return;
    setActingId(refund.id);
    setActionError(null);
    try {
      await processRefund(token, refund.id);
      await load();
    } catch (err) {
      // A NotImplementedError from the still-unwired PNB gateway surfaces
      // here as a plain 500 - see docs/architecture/PHASE_14_PAYMENTS.md.
      // The refund itself is safely left in PROCESSING either way (never
      // silently marked FAILED for an unknown-outcome gateway error).
      setActionError(
        err instanceof PaymentsApiError
          ? err.message
          : "The payment gateway integration is not yet available - see PHASE_14_PAYMENTS.md.",
      );
    } finally {
      setActingId(null);
      await load();
    }
  };

  const handleReject = async (reason: string) => {
    const token = getAccessToken();
    if (!token || !rejectTarget) return;
    setActingId(rejectTarget.id);
    setActionError(null);
    try {
      await rejectRefund(token, rejectTarget.id, reason);
      setRejectTarget(null);
      await load();
    } catch (err) {
      setActionError(err instanceof PaymentsApiError ? err.message : "Unable to reject this refund.");
    } finally {
      setActingId(null);
    }
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2 rounded border border-neutral-200 bg-white p-3">
        <FilterSelect label="Status" value={status} options={REFUND_STATUSES} onChange={(v) => { setPage(1); setStatus(v); }} />
        {status && (
          <button onClick={() => { setStatus(""); setPage(1); }} className="text-sm font-medium text-primary-700 hover:underline">
            Clear filter
          </button>
        )}
      </div>

      {actionError && (
        <p className="mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">
          {actionError}
        </p>
      )}

      <div className="overflow-hidden rounded border border-neutral-200 bg-white">
        {loading ? (
          <TableSkeleton rows={6} columns={6} />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon="credit-card"
            title="No refunds found"
            message={status ? "No refunds match the current filter." : "There are genuinely no refund requests yet - one is created automatically when a paid order is cancelled."}
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                  <tr>
                    <th className="px-4 py-2 font-medium">Refund</th>
                    <th className="px-4 py-2 font-medium">Order / Payment</th>
                    <th className="px-4 py-2 font-medium">Amount</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Requested</th>
                    {canManage && <th className="px-4 py-2 font-medium">Actions</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {data.items.map((refund) => {
                    const actions = refundActionsFor(refund.status);
                    const busy = actingId === refund.id;
                    return (
                      <tr key={refund.id} className="hover:bg-neutral-50">
                        <td className="px-4 py-3 font-medium text-primary-900">#{refund.id}</td>
                        <td className="px-4 py-3">
                          <button
                            onClick={() => router.push(`/payments/${refund.payment_id}`)}
                            className="text-primary-700 hover:underline"
                          >
                            Order #{refund.order_id} · Payment #{refund.payment_id}
                          </button>
                        </td>
                        <td className="px-4 py-3 font-medium text-neutral-800">{formatMoney(refund.amount, refund.currency)}</td>
                        <td className="px-4 py-3">
                          <StatusBadge status={refund.status} />
                          {refund.rejection_reason && (
                            <p className="mt-0.5 text-xs text-neutral-500">{refund.rejection_reason}</p>
                          )}
                        </td>
                        <td className="px-4 py-3 text-neutral-500">{formatDateTime(refund.requested_at)}</td>
                        {canManage && (
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              {actions.approve && (
                                <button
                                  disabled={busy}
                                  onClick={() => handleApprove(refund)}
                                  className="rounded border border-status-success/40 px-2.5 py-1 text-xs font-semibold text-status-success hover:bg-status-successLight disabled:opacity-50"
                                >
                                  {busy ? "Working..." : "Approve"}
                                </button>
                              )}
                              {actions.reject && (
                                <button
                                  disabled={busy}
                                  onClick={() => setRejectTarget(refund)}
                                  className="rounded border border-status-danger/40 px-2.5 py-1 text-xs font-semibold text-status-danger hover:bg-status-dangerLight disabled:opacity-50"
                                >
                                  Reject
                                </button>
                              )}
                              {actions.process && (
                                <button
                                  disabled={busy}
                                  onClick={() => handleProcess(refund)}
                                  className="rounded border border-primary-700/40 px-2.5 py-1 text-xs font-semibold text-primary-800 hover:bg-primary-50 disabled:opacity-50"
                                >
                                  {busy ? "Working..." : "Process"}
                                </button>
                              )}
                              {!actions.approve && !actions.reject && !actions.process && (
                                <span className="text-xs text-neutral-400">No action available</span>
                              )}
                            </div>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
          </>
        )}
      </div>

      <ConfirmDialog
        open={Boolean(rejectTarget)}
        title={`Reject refund #${rejectTarget?.id ?? ""}?`}
        description="This permanently rejects the refund request. The customer will not be refunded."
        confirmLabel="Reject refund"
        danger
        requireReason
        loading={actingId === rejectTarget?.id}
        error={actionError}
        onConfirm={handleReject}
        onCancel={() => {
          setRejectTarget(null);
          setActionError(null);
        }}
      />
    </div>
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
