"use client";

import React, { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  ADJUSTMENT_REASONS,
  AdminInventoryLotDetail,
  adjustStock,
  fetchLocations,
  fetchLotDetail,
  InventoryApiError,
  Location,
  reconcileStock,
  transferStock,
} from "@/lib/inventory";
import { formatDate, formatDateTime } from "@/lib/format";
import { ErrorState } from "@/components/ErrorState";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Icon } from "@/components/icons";

type ActiveDialog = "adjust" | "reconcile" | "transfer" | null;

export default function InventoryLotDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const lotId = Number(id);
  const { getAccessToken, user } = useAuth();
  const router = useRouter();

  const [lot, setLot] = useState<AdminInventoryLotDetail | null>(null);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<ActiveDialog>(null);

  const canAdjust = user && hasPermission(user.roles, "inventory.adjust");
  const canReconcile = user && hasPermission(user.roles, "inventory.reconcile");
  const canTransfer = user && hasPermission(user.roles, "inventory.transfer");

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setLot(await fetchLotDetail(token, lotId));
    } catch (err) {
      setError(err instanceof InventoryApiError ? err.message : "Unable to load this inventory lot.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lotId]);

  useEffect(() => {
    load();
    const token = getAccessToken();
    if (token) fetchLocations(token).then(setLocations).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  if (loading) return <div className="animate-pulse text-sm text-neutral-400">Loading inventory...</div>;
  if (error || !lot) return <ErrorState message={error ?? "Inventory lot not found."} onRetry={load} />;

  return (
    <div className="mx-auto max-w-4xl">
      <button onClick={() => router.push("/inventory")} className="mb-4 flex items-center gap-1 text-sm text-neutral-500 hover:text-primary-800">
        <Icon name="chevron-left" size={14} /> Back to inventory
      </button>

      <div className="mb-6 flex items-start gap-4">
        <div className="h-20 w-20 shrink-0 overflow-hidden rounded bg-neutral-100">
          {lot.product_image_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={lot.product_image_url} alt="" className="h-full w-full object-cover" />
          )}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="font-display text-2xl font-semibold text-primary-900">{lot.product_name}</h1>
            <StatusBadge status={lot.operational_status} />
          </div>
          <p className="mt-1 text-sm text-neutral-500">
            {lot.category_name} · {lot.sku} · {lot.variant_name} ({lot.unit})
          </p>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-3">
        <StockNumber label="On hand" value={lot.on_hand} />
        <StockNumber label="Reserved" value={lot.reserved} />
        <StockNumber label="Available" value={lot.available} emphasize />
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {canAdjust && (
          <ActionButton onClick={() => setDialog("adjust")} icon="package" label="Adjust stock" />
        )}
        {canReconcile && (
          <ActionButton onClick={() => setDialog("reconcile")} icon="file-text" label="Reconcile" />
        )}
        {canTransfer && (
          <ActionButton onClick={() => setDialog("transfer")} icon="truck" label="Transfer" />
        )}
      </div>

      <Section title="Warehouse">
        <Row label="Name" value={lot.location_name} />
        <Row label="Code" value={lot.location_code} />
        <Row label="City" value={lot.location_city} />
        <div className="flex items-center justify-between py-1.5 text-sm">
          <span className="text-neutral-500">Status</span>
          <StatusBadge status={lot.location_status} />
        </div>
      </Section>

      <Section title="Batch / lot traceability">
        <Row label="Batch code" value={lot.batch.batch_code} />
        <Row label="Harvest date" value={formatDate(lot.batch.harvest_date)} />
        {lot.batch.expiry_date && <Row label="Expiry date" value={formatDate(lot.batch.expiry_date)} />}
        {lot.batch.supplier_name && <Row label="Supplier" value={lot.batch.supplier_name} />}
        {lot.batch.receiving_reference && <Row label="Receiving reference" value={lot.batch.receiving_reference} />}
        <div className="flex items-center justify-between py-1.5 text-sm">
          <span className="text-neutral-500">Batch status</span>
          <StatusBadge status={lot.batch.status} />
        </div>
      </Section>

      <Section title={`Stock movements (${lot.recent_movements.length})`}>
        {lot.recent_movements.length === 0 ? (
          <p className="text-sm text-neutral-400">No movements recorded yet.</p>
        ) : (
          <div className="divide-y divide-neutral-100">
            {lot.recent_movements.map((m) => (
              <div key={m.id} className="flex items-start justify-between py-2 text-sm">
                <div>
                  <p className="font-medium text-neutral-800">
                    {m.movement_type.replaceAll("_", " ")} — {m.quantity}
                  </p>
                  {m.remarks && <p className="text-xs text-neutral-500">{m.remarks}</p>}
                </div>
                <p className="shrink-0 text-xs text-neutral-400">{formatDateTime(m.occurred_at)}</p>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title={`Related orders (${lot.related_orders.length})`}>
        {lot.related_orders.length === 0 ? (
          <p className="text-sm text-neutral-400">No orders have reserved or consumed stock from this lot.</p>
        ) : (
          <div className="divide-y divide-neutral-100">
            {lot.related_orders.map((o) => (
              <div key={o.order_id} className="flex items-center justify-between py-2 text-sm">
                <a href={`/orders/${o.order_id}`} className="font-medium text-primary-900 hover:underline">{o.order_number}</a>
                <span className="text-neutral-600">{o.reserved_quantity} {lot.unit}</span>
                <StatusBadge status={o.reservation_status} />
              </div>
            ))}
          </div>
        )}
      </Section>

      <AdjustDialog open={dialog === "adjust"} lot={lot} onClose={() => setDialog(null)} onDone={load} />
      <ReconcileDialog open={dialog === "reconcile"} lot={lot} onClose={() => setDialog(null)} onDone={load} />
      <TransferDialog open={dialog === "transfer"} lot={lot} locations={locations} onClose={() => setDialog(null)} onDone={load} />
    </div>
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

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="text-neutral-500">{label}</span>
      <span className="font-medium text-neutral-800">{value}</span>
    </div>
  );
}

function StockNumber({ label, value, emphasize }: { label: string; value: string; emphasize?: boolean }) {
  return (
    <div className="rounded border border-neutral-200 bg-white p-4 text-center">
      <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">{label}</p>
      <p className={`mt-1 font-display text-2xl font-semibold ${emphasize ? "text-primary-900" : "text-neutral-600"}`}>{value}</p>
    </div>
  );
}

function ActionButton({ onClick, icon, label }: { onClick: () => void; icon: Parameters<typeof Icon>[0]["name"]; label: string }) {
  return (
    <button onClick={onClick} className="flex items-center gap-1.5 rounded border border-neutral-300 px-3 py-1.5 text-sm font-semibold text-primary-800 hover:bg-neutral-50">
      <Icon name={icon} size={14} /> {label}
    </button>
  );
}

function AdjustDialog({ open, lot, onClose, onDone }: { open: boolean; lot: AdminInventoryLotDetail; onClose: () => void; onDone: () => void }) {
  const { getAccessToken } = useAuth();
  const [direction, setDirection] = useState<"ADJUSTMENT_IN" | "ADJUSTMENT_OUT" | "DAMAGE" | "WASTE">("ADJUSTMENT_IN");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState<string>(ADJUSTMENT_REASONS[0]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleConfirm = async () => {
    const token = getAccessToken();
    if (!token || !quantity) return;
    setSaving(true);
    setError(null);
    try {
      await adjustStock(token, lot.id, { movement_type: direction, quantity, remarks: reason });
      onClose();
      onDone();
    } catch (err) {
      setError(err instanceof InventoryApiError ? err.message : "Unable to adjust stock.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-sm rounded bg-white p-6 shadow-xl">
        <h2 className="mb-1 font-display text-lg font-semibold text-primary-900">Adjust stock</h2>
        <p className="mb-4 text-sm text-neutral-500">Current: {lot.on_hand} {lot.unit}</p>

        <div className="mb-3 flex gap-2">
          {(["ADJUSTMENT_IN", "ADJUSTMENT_OUT", "DAMAGE", "WASTE"] as const).map((d) => (
            <button
              key={d}
              onClick={() => setDirection(d)}
              className={`rounded border px-2 py-1 text-xs font-semibold ${direction === d ? "border-primary-700 bg-primary-800 text-white" : "border-neutral-300 text-neutral-600"}`}
            >
              {d.replaceAll("_", " ")}
            </button>
          ))}
        </div>

        <input type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="Quantity" className="mb-3 w-full rounded border border-neutral-300 px-3 py-2 text-sm" />

        <select value={reason} onChange={(e) => setReason(e.target.value)} className="mb-3 w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm">
          {ADJUSTMENT_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>

        {error && <p className="mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>}

        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="rounded border border-neutral-300 px-4 py-2 text-sm">Cancel</button>
          <button onClick={handleConfirm} disabled={saving || !quantity} className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">
            {saving ? "Applying..." : "Apply adjustment"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ReconcileDialog({ open, lot, onClose, onDone }: { open: boolean; lot: AdminInventoryLotDetail; onClose: () => void; onDone: () => void }) {
  const { getAccessToken } = useAuth();
  const [physicalCount, setPhysicalCount] = useState(lot.on_hand);
  const [reason, setReason] = useState<string>(ADJUSTMENT_REASONS[1]);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const difference = physicalCount ? (Number.parseFloat(physicalCount) - Number.parseFloat(lot.on_hand)).toFixed(3) : "0";

  return (
    <ConfirmDialog
      open={open}
      title="Reconcile physical count"
      description={`System stock: ${lot.on_hand} ${lot.unit}. Difference: ${difference}. This creates the corresponding stock movement.`}
      confirmLabel="Submit reconciliation"
      loading={saving}
      error={error}
      onCancel={onClose}
      onConfirm={async () => {
        const token = getAccessToken();
        if (!token) return;
        setSaving(true);
        setError(null);
        try {
          await reconcileStock(token, lot.id, { physical_count: physicalCount, reason, notes: notes || undefined });
          onClose();
          onDone();
        } catch (err) {
          setError(err instanceof InventoryApiError ? err.message : "Unable to reconcile stock.");
        } finally {
          setSaving(false);
        }
      }}
    >
      <input type="number" value={physicalCount} onChange={(e) => setPhysicalCount(e.target.value)} placeholder="Physical count" className="mt-2 w-full rounded border border-neutral-300 px-3 py-2 text-sm" />
      <select value={reason} onChange={(e) => setReason(e.target.value)} className="mt-2 w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm">
        {ADJUSTMENT_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
      </select>
      <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Notes (optional)" rows={2} className="mt-2 w-full rounded border border-neutral-300 px-3 py-2 text-sm" />
    </ConfirmDialog>
  );
}

function TransferDialog({
  open,
  lot,
  locations,
  onClose,
  onDone,
}: {
  open: boolean;
  lot: AdminInventoryLotDetail;
  locations: Location[];
  onClose: () => void;
  onDone: () => void;
}) {
  const { getAccessToken } = useAuth();
  const [destinationId, setDestinationId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const otherLocations = locations.filter((l) => l.id !== lot.location_id);

  const handleConfirm = async () => {
    const token = getAccessToken();
    if (!token || !destinationId || !quantity) return;
    setSaving(true);
    setError(null);
    try {
      await transferStock(token, { source_lot_id: lot.id, destination_location_id: Number(destinationId), quantity });
      onClose();
      onDone();
    } catch (err) {
      setError(err instanceof InventoryApiError ? err.message : "Unable to transfer stock.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-sm rounded bg-white p-6 shadow-xl">
        <h2 className="mb-1 font-display text-lg font-semibold text-primary-900">Transfer stock</h2>
        <p className="mb-4 text-sm text-neutral-500">From {lot.location_name} · Available: {lot.available} {lot.unit}</p>

        <select value={destinationId} onChange={(e) => setDestinationId(e.target.value)} className="mb-3 w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm">
          <option value="">Destination warehouse</option>
          {otherLocations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
        </select>

        <input type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="Quantity" className="mb-3 w-full rounded border border-neutral-300 px-3 py-2 text-sm" />

        {error && <p className="mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>}

        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="rounded border border-neutral-300 px-4 py-2 text-sm">Cancel</button>
          <button onClick={handleConfirm} disabled={saving || !destinationId || !quantity} className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">
            {saving ? "Transferring..." : "Transfer"}
          </button>
        </div>
      </div>
    </div>
  );
}
