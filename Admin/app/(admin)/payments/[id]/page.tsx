"use client";

import React, { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  AdminPaymentDetail,
  approveRefund,
  fetchAdminPaymentDetail,
  PaymentsApiError,
  processRefund,
  refundActionsFor,
  rejectRefund,
} from "@/lib/payments";
import { formatDateTime, formatMoney } from "@/lib/format";
import { ErrorState } from "@/components/ErrorState";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Icon } from "@/components/icons";

export default function PaymentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const paymentId = Number(id);
  const { getAccessToken, user } = useAuth();
  const router = useRouter();

  const [payment, setPayment] = useState<AdminPaymentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [rejectOpen, setRejectOpen] = useState(false);
  const [acting, setActing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setPayment(await fetchAdminPaymentDetail(token, paymentId));
    } catch (err) {
      setError(err instanceof PaymentsApiError ? err.message : "Unable to load this payment.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paymentId]);

  useEffect(() => {
    load();
  }, [load]);

  const canManage = Boolean(user && hasPermission(user.roles, "orders.refund"));
  const refund = payment?.refund ?? null;
  const actions = refund ? refundActionsFor(refund.status) : null;

  const handleApprove = async () => {
    const token = getAccessToken();
    if (!token || !refund) return;
    setActing(true);
    setActionError(null);
    try {
      await approveRefund(token, refund.id);
      await load();
    } catch (err) {
      setActionError(err instanceof PaymentsApiError ? err.message : "Unable to approve this refund.");
    } finally {
      setActing(false);
    }
  };

  const handleProcess = async () => {
    const token = getAccessToken();
    if (!token || !refund) return;
    setActing(true);
    setActionError(null);
    try {
      await processRefund(token, refund.id);
    } catch (err) {
      // A NotImplementedError from the still-unwired PNB gateway surfaces
      // as a plain 500 - see docs/architecture/PHASE_14_PAYMENTS.md. The
      // refund is safely left in PROCESSING regardless (never silently
      // marked FAILED for an unknown-outcome gateway error).
      setActionError(
        err instanceof PaymentsApiError
          ? err.message
          : "The payment gateway integration is not yet available - see PHASE_14_PAYMENTS.md.",
      );
    } finally {
      setActing(false);
      await load();
    }
  };

  const handleReject = async (reason: string) => {
    const token = getAccessToken();
    if (!token || !refund) return;
    setActing(true);
    setActionError(null);
    try {
      await rejectRefund(token, refund.id, reason);
      setRejectOpen(false);
      await load();
    } catch (err) {
      setActionError(err instanceof PaymentsApiError ? err.message : "Unable to reject this refund.");
    } finally {
      setActing(false);
    }
  };

  if (loading) {
    return <div className="animate-pulse text-sm text-neutral-400">Loading payment...</div>;
  }
  if (error || !payment) {
    return <ErrorState message={error ?? "Payment not found."} onRetry={load} />;
  }

  return (
    <div className="mx-auto max-w-4xl">
      <button onClick={() => router.push("/payments")} className="mb-4 flex items-center gap-1 text-sm text-neutral-500 hover:text-primary-800">
        <Icon name="chevron-left" size={14} /> Back to payments
      </button>

      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-primary-900">Payment #{payment.id}</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Order <button onClick={() => router.push(`/orders/${payment.order_id}`)} className="text-primary-700 hover:underline">{payment.order_number}</button>
            {" · "}Created {formatDateTime(payment.created_at)}
          </p>
        </div>
        <StatusBadge status={payment.status} />
      </div>

      <Section title="Customer">
        <Row label="Name" value={payment.customer_name} />
        <Row label="Email" value={payment.customer_email} />
      </Section>

      <Section title="Payment">
        <Row label="Method" value={payment.payment_method === "COD" ? "Cash on Delivery" : payment.payment_method} />
        <div className="flex items-center justify-between py-1.5 text-sm">
          <span className="text-neutral-500">Status</span>
          <StatusBadge status={payment.status} />
        </div>
        <Row label="Amount" value={formatMoney(payment.amount, payment.currency)} />
        {payment.gateway_name && <Row label="Gateway" value={payment.gateway_name} />}
        {payment.gateway_order_id && <Row label="Gateway order id" value={payment.gateway_order_id} />}
        {payment.paid_at && <Row label="Paid at" value={formatDateTime(payment.paid_at)} />}
      </Section>

      <Section title={`Attempt history (${payment.transactions.length})`}>
        {payment.transactions.length === 0 ? (
          <p className="py-2 text-sm text-neutral-400">
            No gateway attempts recorded - expected for a Cash on Delivery payment, which never calls a gateway.
          </p>
        ) : (
          <div className="divide-y divide-neutral-100">
            {payment.transactions.map((t) => (
              <div key={t.id} className="flex items-center justify-between py-2 text-sm">
                <div>
                  <p className="font-medium text-neutral-800">
                    {t.transaction_type === "REFUND" ? "Refund attempt" : "Payment attempt"} · {formatMoney(t.amount, t.currency)}
                  </p>
                  <p className="text-xs text-neutral-500">
                    {t.gateway_name ?? "—"}
                    {t.gateway_transaction_id && ` · ${t.gateway_transaction_id}`} · Initiated {formatDateTime(t.initiated_at)}
                  </p>
                  {t.failure_reason && <p className="mt-0.5 text-xs text-status-danger">{t.failure_reason}</p>}
                </div>
                <StatusBadge status={t.status} />
              </div>
            ))}
          </div>
        )}
      </Section>

      {refund && actions && (
        <Section title="Refund">
          <div className="flex items-center justify-between py-1.5 text-sm">
            <span className="text-neutral-500">Status</span>
            <StatusBadge status={refund.status} />
          </div>
          <Row label="Amount" value={formatMoney(refund.amount, refund.currency)} />
          <Row label="Requested at" value={formatDateTime(refund.requested_at)} />
          {refund.approved_at && <Row label="Approved/rejected at" value={formatDateTime(refund.approved_at)} />}
          {refund.rejection_reason && <Row label="Rejection reason" value={refund.rejection_reason} />}
          {refund.processed_at && <Row label="Processed at" value={formatDateTime(refund.processed_at)} />}

          {actionError && (
            <p className="mt-2 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">
              {actionError}
            </p>
          )}

          {canManage && (actions.approve || actions.reject || actions.process) && (
            <div className="mt-3 flex items-center gap-2 border-t border-neutral-100 pt-3">
              {actions.approve && (
                <button
                  disabled={acting}
                  onClick={handleApprove}
                  className="rounded border border-status-success/40 px-3 py-1.5 text-sm font-semibold text-status-success hover:bg-status-successLight disabled:opacity-50"
                >
                  {acting ? "Working..." : "Approve refund"}
                </button>
              )}
              {actions.reject && (
                <button
                  disabled={acting}
                  onClick={() => setRejectOpen(true)}
                  className="rounded border border-status-danger/40 px-3 py-1.5 text-sm font-semibold text-status-danger hover:bg-status-dangerLight disabled:opacity-50"
                >
                  Reject refund
                </button>
              )}
              {actions.process && (
                <button
                  disabled={acting}
                  onClick={handleProcess}
                  className="rounded border border-primary-700/40 px-3 py-1.5 text-sm font-semibold text-primary-800 hover:bg-primary-50 disabled:opacity-50"
                >
                  {acting ? "Working..." : "Process refund"}
                </button>
              )}
            </div>
          )}
        </Section>
      )}

      <ConfirmDialog
        open={rejectOpen}
        title="Reject this refund?"
        description="This permanently rejects the refund request. The customer will not be refunded."
        confirmLabel="Reject refund"
        danger
        requireReason
        loading={acting}
        error={actionError}
        onConfirm={handleReject}
        onCancel={() => {
          setRejectOpen(false);
          setActionError(null);
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
