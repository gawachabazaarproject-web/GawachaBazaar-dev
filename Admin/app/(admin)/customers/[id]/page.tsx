"use client";

import React, { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  AdminCustomerDetail,
  CustomerApiError,
  CustomerNote,
  CustomerOrderListItem,
  CustomerPromotionRedemptionRow,
  CustomerTimelineEvent,
  PendingContactChange,
  cancelContactChange,
  confirmContactChange,
  createCustomerNote,
  fetchCustomerAddresses,
  fetchCustomerDetail,
  fetchCustomerNotes,
  fetchCustomerOrders,
  fetchCustomerPromotions,
  fetchCustomerTimeline,
  requestContactChange,
  setCustomerStatus,
  updateCustomerNote,
} from "@/lib/customers";
import { CustomerAddress } from "@/lib/customers";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState } from "@/components/ErrorState";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { Icon } from "@/components/icons";

export default function CustomerDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const customerId = Number(id);
  const { getAccessToken, user } = useAuth();
  const router = useRouter();

  const [customer, setCustomer] = useState<AdminCustomerDetail | null>(null);
  const [orders, setOrders] = useState<CustomerOrderListItem[] | null>(null);
  const [promotions, setPromotions] = useState<CustomerPromotionRedemptionRow[] | null>(null);
  const [addresses, setAddresses] = useState<CustomerAddress[] | null>(null);
  const [timeline, setTimeline] = useState<CustomerTimelineEvent[] | null>(null);
  const [notes, setNotes] = useState<CustomerNote[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [statusAction, setStatusAction] = useState<"INACTIVE" | "SUSPENDED" | "ACTIVE" | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

  const [newNote, setNewNote] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [editingNoteText, setEditingNoteText] = useState("");

  const canManageStatus = user && hasPermission(user.roles, "customers.manage_status");
  const canManageNotes = user && hasPermission(user.roles, "customers.notes");
  const canManageContact = user && hasPermission(user.roles, "customers.manage_contact");

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await fetchCustomerDetail(token, customerId);
      setCustomer(detail);
      fetchCustomerOrders(token, customerId).then((r) => setOrders(r.items)).catch(() => undefined);
      fetchCustomerPromotions(token, customerId).then((r) => setPromotions(r.items)).catch(() => undefined);
      fetchCustomerAddresses(token, customerId).then(setAddresses).catch(() => undefined);
      fetchCustomerTimeline(token, customerId).then(setTimeline).catch(() => undefined);
      if (canManageNotes) fetchCustomerNotes(token, customerId).then(setNotes).catch(() => undefined);
    } catch (err) {
      setError(err instanceof CustomerApiError ? err.message : "Unable to load this customer.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerId, canManageNotes]);

  useEffect(() => {
    load();
  }, [load]);

  const runStatusChange = async (reason: string) => {
    const token = getAccessToken();
    if (!token || !statusAction) return;
    setStatusLoading(true);
    setStatusError(null);
    try {
      const updated = await setCustomerStatus(token, customerId, statusAction, reason || undefined);
      setCustomer(updated);
      setStatusAction(null);
    } catch (err) {
      setStatusError(err instanceof CustomerApiError ? err.message : "Unable to change account status.");
    } finally {
      setStatusLoading(false);
    }
  };

  const handleAddNote = async () => {
    const token = getAccessToken();
    if (!token || !newNote.trim()) return;
    setSavingNote(true);
    try {
      const note = await createCustomerNote(token, customerId, newNote.trim());
      setNotes((prev) => [note, ...(prev ?? [])]);
      setNewNote("");
    } catch {
      // Surfaced via the note list staying unchanged - the input keeps the
      // draft text so nothing is lost.
    } finally {
      setSavingNote(false);
    }
  };

  const handleSaveEditedNote = async () => {
    const token = getAccessToken();
    if (!token || editingNoteId === null || !editingNoteText.trim()) return;
    try {
      const updated = await updateCustomerNote(token, editingNoteId, editingNoteText.trim());
      setNotes((prev) => (prev ?? []).map((n) => (n.id === updated.id ? updated : n)));
      setEditingNoteId(null);
    } catch {
      // Leave the row in edit mode with the attempted text on failure.
    }
  };

  if (loading) return <div className="animate-pulse text-sm text-neutral-400">Loading customer...</div>;
  if (error || !customer) return <ErrorState message={error ?? "Customer not found."} onRetry={load} />;

  return (
    <div className="mx-auto max-w-4xl">
      <button onClick={() => router.push("/customers")} className="mb-4 flex items-center gap-1 text-sm text-neutral-500 hover:text-primary-800">
        <Icon name="chevron-left" size={14} /> Back to customers
      </button>

      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-2xl font-semibold text-primary-900">{customer.name}</h1>
            <StatusBadge status={customer.account_status} />
          </div>
          <p className="mt-1 text-sm text-neutral-500">
            #{customer.id} · {customer.email} · {customer.phone}
          </p>
          <p className="mt-1 text-xs text-neutral-400">
            Roles: {customer.roles.join(", ")}
            {customer.is_bulk_customer && " · Bulk/B2B customer"} · Joined {formatDate(customer.created_at)}
          </p>
        </div>
        {canManageStatus && (
          <div className="flex shrink-0 gap-2">
            {customer.account_status !== "ACTIVE" && (
              <ActionButton label="Activate" onClick={() => setStatusAction("ACTIVE")} />
            )}
            {customer.account_status !== "SUSPENDED" && (
              <ActionButton label="Suspend" danger onClick={() => setStatusAction("SUSPENDED")} />
            )}
            {customer.account_status !== "INACTIVE" && (
              <ActionButton label="Disable" danger onClick={() => setStatusAction("INACTIVE")} />
            )}
          </div>
        )}
      </div>

      {/* Summary */}
      <Section title="Summary">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Metric label="Total orders" value={customer.summary.total_orders} />
          <Metric label="Completed" value={customer.summary.completed_orders} />
          <Metric label="Cancelled" value={customer.summary.cancelled_orders} />
          <Metric label="Pending" value={customer.summary.pending_orders} />
          <Metric label="Total spend" value={formatMoney(customer.summary.total_spend)} />
          <Metric
            label="Avg order value"
            value={customer.summary.average_order_value ? formatMoney(customer.summary.average_order_value) : "—"}
          />
          <Metric label="First order" value={customer.summary.first_order_at ? formatDate(customer.summary.first_order_at) : "—"} />
          <Metric label="Last order" value={customer.summary.last_order_at ? formatDate(customer.summary.last_order_at) : "—"} />
        </div>
        <p className="mt-3 text-xs text-neutral-400">
          Total spend and average order value are computed only from COMPLETED (delivered) orders - the only
          orders that represent realized revenue.
        </p>
      </Section>

      {/* Orders */}
      <Section title={`Orders (${orders?.length ?? 0})`}>
        {!orders || orders.length === 0 ? (
          <EmptyState icon="package" title="No orders yet" message="This customer hasn't placed an order." />
        ) : (
          <div className="divide-y divide-neutral-100">
            {orders.map((o) => (
              <div
                key={o.id}
                onClick={() => router.push(`/orders/${o.id}`)}
                className="flex cursor-pointer items-center justify-between py-2.5 text-sm hover:bg-neutral-50"
              >
                <div>
                  <p className="font-mono text-xs text-primary-800">{o.order_number}</p>
                  <p className="text-xs text-neutral-400">{formatDateTime(o.placed_at)} · {o.item_count} item(s)</p>
                </div>
                <div className="flex items-center gap-3">
                  {o.applied_promo_code && (
                    <span className="rounded bg-secondary-100 px-1.5 py-0.5 text-xs font-mono text-secondary-700">
                      {o.applied_promo_code}
                    </span>
                  )}
                  <span className="text-neutral-700">{formatMoney(o.total_amount, o.currency)}</span>
                  <StatusBadge status={o.status} />
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Promotions */}
      <Section title={`Promotion usage (${promotions?.length ?? 0})`}>
        {!promotions || promotions.length === 0 ? (
          <EmptyState icon="tag" title="No promotions used" message="This customer hasn't redeemed a coupon or promotion." />
        ) : (
          <div className="divide-y divide-neutral-100">
            {promotions.map((p) => (
              <div key={p.id} className="flex items-center justify-between py-2.5 text-sm">
                <div>
                  <a href={`/promotions/${p.promotion_id}`} className="font-medium text-primary-900 hover:underline">
                    {p.promotion_name}
                  </a>
                  <p className="text-xs text-neutral-400">
                    {p.promotion_code ?? "automatic"} · on{" "}
                    <a href={`/orders/${p.order_id}`} className="font-mono text-primary-700 hover:underline">
                      {p.order_number}
                    </a>
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-neutral-700">-{formatMoney(p.discount_amount)}</span>
                  <StatusBadge status={p.status} />
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Reviews - honest disclosure: no Review domain exists in the
          backend today (confirmed: no Review model/service/endpoint
          anywhere), so this section is never fabricated. */}
      <Section title="Reviews">
        <p className="text-sm text-neutral-400">
          There is no product review system in the backend yet - nothing to show here until that domain exists.
        </p>
      </Section>

      {/* Timeline */}
      <Section title="Activity timeline">
        {!timeline || timeline.length === 0 ? (
          <p className="text-sm text-neutral-400">No recorded activity yet.</p>
        ) : (
          <div className="space-y-3">
            {timeline.map((event, i) => (
              <div key={i} className="flex items-start justify-between text-sm">
                <div>
                  <p className="text-neutral-800">{event.title}</p>
                  {event.description && <p className="text-xs text-neutral-500">{event.description}</p>}
                </div>
                <p className="shrink-0 text-xs text-neutral-400">{formatDateTime(event.occurred_at)}</p>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Addresses */}
      <Section title={`Addresses (${addresses?.length ?? 0})`}>
        {!addresses || addresses.length === 0 ? (
          <EmptyState icon="box" title="No saved addresses" message="This customer hasn't saved a delivery address." />
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {addresses.map((a) => (
              <div key={a.id} className="rounded border border-neutral-200 p-3 text-sm">
                <div className="mb-1 flex items-center gap-2">
                  <span className="font-medium text-primary-900">{a.label}</span>
                  {a.is_default && (
                    <span className="rounded bg-primary-100 px-1.5 py-0.5 text-xs font-semibold text-primary-800">DEFAULT</span>
                  )}
                </div>
                <p className="text-neutral-600">
                  {a.address_line_1}
                  {a.address_line_2 ? `, ${a.address_line_2}` : ""}, {a.city}, {a.state} {a.postal_code}
                </p>
                <p className="mt-1 text-xs text-neutral-400">Saved {formatDate(a.created_at)}</p>
              </div>
            ))}
          </div>
        )}
        <p className="mt-3 text-xs text-neutral-400">
          A customer's current address book is not necessarily what was used on a past order - each order keeps
          its own delivery-address snapshot (see that order's detail page).
        </p>
      </Section>

      {/* Account information - verification-backed email/phone change.
          Never a raw PATCH: the new value only lands once whoever controls
          it proves that with the code sent there (see
          app/services/contact_change methods on the backend's
          CustomerService). */}
      {canManageContact && (
        <Section title="Account information">
          <ContactChangeField
            field="EMAIL"
            label="Email"
            currentValue={customer.email}
            pending={customer.pending_email_change}
            customerId={customer.id}
            onChanged={setCustomer}
            onCancelled={load}
          />
          <ContactChangeField
            field="PHONE"
            label="Phone"
            currentValue={customer.phone}
            pending={customer.pending_phone_change}
            customerId={customer.id}
            onChanged={setCustomer}
            onCancelled={load}
          />
        </Section>
      )}

      {/* Notes */}
      {canManageNotes && (
        <Section title="Support notes">
          <div className="mb-3 flex gap-2">
            <textarea
              value={newNote}
              onChange={(e) => setNewNote(e.target.value)}
              placeholder="Add an internal note about this customer (not visible to them)..."
              rows={2}
              className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
            <button
              onClick={handleAddNote}
              disabled={!newNote.trim() || savingNote}
              className="self-start rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
            >
              {savingNote ? "Saving..." : "Add note"}
            </button>
          </div>
          {!notes || notes.length === 0 ? (
            <p className="text-sm text-neutral-400">No notes yet.</p>
          ) : (
            <div className="space-y-3">
              {notes.map((n) => (
                <div key={n.id} className="rounded border border-neutral-200 p-3 text-sm">
                  {editingNoteId === n.id ? (
                    <div>
                      <textarea
                        value={editingNoteText}
                        onChange={(e) => setEditingNoteText(e.target.value)}
                        rows={2}
                        className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
                      />
                      <div className="mt-2 flex gap-2">
                        <button onClick={handleSaveEditedNote} className="text-xs font-semibold text-primary-700 hover:underline">
                          Save
                        </button>
                        <button onClick={() => setEditingNoteId(null)} className="text-xs text-neutral-500 hover:underline">
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <p className="text-neutral-800">{n.note}</p>
                      <div className="mt-1 flex items-center justify-between text-xs text-neutral-400">
                        <span>
                          {n.author_name} · {formatDateTime(n.updated_at)}
                          {n.updated_at !== n.created_at && " (edited)"}
                        </span>
                        <button
                          onClick={() => { setEditingNoteId(n.id); setEditingNoteText(n.note); }}
                          className="font-semibold text-primary-700 hover:underline"
                        >
                          Edit
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </Section>
      )}

      <ConfirmDialog
        open={statusAction !== null}
        title={statusDialogCopy(statusAction).title}
        description={statusDialogCopy(statusAction).description}
        confirmLabel={statusDialogCopy(statusAction).confirmLabel}
        danger={statusAction === "INACTIVE" || statusAction === "SUSPENDED"}
        requireReason={statusAction === "INACTIVE" || statusAction === "SUSPENDED"}
        loading={statusLoading}
        error={statusError}
        onConfirm={runStatusChange}
        onCancel={() => { setStatusAction(null); setStatusError(null); }}
      />
    </div>
  );
}

function statusDialogCopy(action: "INACTIVE" | "SUSPENDED" | "ACTIVE" | null) {
  switch (action) {
    case "INACTIVE":
      return {
        title: "Disable this customer's account?",
        description: "They will be immediately signed out of every device and unable to log in, browse, or check out until reactivated. This does not affect their past orders.",
        confirmLabel: "Disable account",
      };
    case "SUSPENDED":
      return {
        title: "Suspend this customer's account?",
        description: "They will be immediately signed out of every device and unable to log in until reactivated. Use this for policy or trust & safety issues rather than a routine disable.",
        confirmLabel: "Suspend account",
      };
    case "ACTIVE":
      return {
        title: "Reactivate this customer's account?",
        description: "They will be able to log in and use their account again immediately.",
        confirmLabel: "Reactivate",
      };
    default:
      return { title: "", description: "", confirmLabel: "Confirm" };
  }
}

/**
 * Self-contained request -> code -> confirm flow for one field (EMAIL or
 * PHONE). The verification code itself is never shown here - in this dev
 * environment there is no real email/SMS gateway, so it's logged
 * server-side (see app/services/notification_gateway.py); a real gateway
 * swap requires no change to this component or the API contract.
 */
function ContactChangeField({
  field,
  label,
  currentValue,
  pending,
  customerId,
  onChanged,
  onCancelled,
}: {
  field: "EMAIL" | "PHONE";
  label: string;
  currentValue: string;
  pending: PendingContactChange | null;
  customerId: number;
  onChanged: (updated: AdminCustomerDetail) => void;
  onCancelled: () => void;
}) {
  const { getAccessToken } = useAuth();
  const [mode, setMode] = useState<"idle" | "request" | "verify">("idle");
  const [newValue, setNewValue] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startRequest = () => {
    setMode("request");
    setNewValue("");
    setError(null);
  };

  const cancel = () => {
    setMode("idle");
    setError(null);
  };

  const handleSendCode = async () => {
    const token = getAccessToken();
    if (!token || !newValue.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await requestContactChange(token, customerId, field, newValue.trim());
      setMode("verify");
      setCode("");
    } catch (err) {
      setError(err instanceof CustomerApiError ? err.message : "Unable to request this change.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    const token = getAccessToken();
    if (!token || code.trim().length !== 6) return;
    setLoading(true);
    setError(null);
    try {
      const updated = await confirmContactChange(token, customerId, field, code.trim());
      onChanged(updated);
      setMode("idle");
    } catch (err) {
      setError(err instanceof CustomerApiError ? err.message : "Unable to verify this code.");
    } finally {
      setLoading(false);
    }
  };

  const handleCancelPending = async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    try {
      await cancelContactChange(token, customerId, field);
      onCancelled();
    } finally {
      setLoading(false);
      setMode("idle");
    }
  };

  // A pending change already exists (e.g. page was reloaded mid-flow) -
  // resume straight into the verify step rather than losing that state.
  const effectiveMode = pending && mode === "idle" ? "verify-existing" : mode;

  return (
    <div className="border-b border-neutral-100 py-3 last:border-b-0">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</p>
          <p className="text-sm text-neutral-800">{currentValue}</p>
        </div>
        {effectiveMode === "idle" && (
          <button onClick={startRequest} className="text-sm font-semibold text-primary-700 hover:underline">
            Change
          </button>
        )}
      </div>

      {effectiveMode === "request" && (
        <div className="mt-2 flex gap-2">
          <input
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder={field === "EMAIL" ? "new@example.com" : "9876543210"}
            className="flex-1 rounded border border-neutral-300 px-3 py-1.5 text-sm"
          />
          <button
            onClick={handleSendCode}
            disabled={!newValue.trim() || loading}
            className="rounded bg-primary-800 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40"
          >
            {loading ? "Sending..." : "Send code"}
          </button>
          <button onClick={cancel} className="text-sm text-neutral-500 hover:underline">
            Cancel
          </button>
        </div>
      )}

      {(effectiveMode === "verify" || effectiveMode === "verify-existing") && (
        <div className="mt-2">
          <p className="text-xs text-neutral-500">
            Verification pending for <span className="font-medium text-neutral-700">{pending?.new_value ?? newValue}</span>
            {pending && `, expires ${formatDateTime(pending.expires_at)}`}. No real email/SMS gateway is configured in
            this environment - check the backend logs for the code.
          </p>
          <div className="mt-2 flex gap-2">
            <input
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="6-digit code"
              className="w-32 rounded border border-neutral-300 px-3 py-1.5 text-sm font-mono"
            />
            <button
              onClick={handleVerify}
              disabled={code.length !== 6 || loading}
              className="rounded bg-primary-800 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40"
            >
              {loading ? "Verifying..." : "Verify"}
            </button>
            <button onClick={handleCancelPending} disabled={loading} className="text-sm text-status-danger hover:underline">
              Cancel request
            </button>
          </div>
        </div>
      )}

      {error && <p className="mt-2 text-xs text-status-danger">{error}</p>}
    </div>
  );
}

function ActionButton({ label, danger, onClick }: { label: string; danger?: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`rounded border px-3 py-1.5 text-sm font-semibold ${
        danger ? "border-status-danger/40 text-status-danger hover:bg-status-dangerLight" : "border-primary-700 text-primary-800 hover:bg-primary-50"
      }`}
    >
      {label}
    </button>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4 rounded border border-neutral-200 bg-white p-4">
      <h2 className="mb-3 font-display text-base font-semibold text-primary-900">{title}</h2>
      {children}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded border border-neutral-200 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">{label}</p>
      <p className="mt-1 font-display text-lg font-semibold text-primary-900">{value}</p>
    </div>
  );
}
