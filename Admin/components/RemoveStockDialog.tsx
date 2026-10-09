"use client";

import React, { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { ADJUSTMENT_REASONS, InventoryApiError, removeStock } from "@/lib/inventory";

export interface RemovableLot {
  id: number;
  product_name: string;
  variant_name: string;
  available: string;
  unit?: string;
}

const REMOVAL_REASONS = ADJUSTMENT_REASONS.filter((r) => r !== "Physical count" && r !== "Receiving correction");

/**
 * Takes stock out of a lot (spoilage, damage, a mistaken receipt...). Either
 * everything that is available or a chosen quantity, always with a reason.
 * Stock already promised to customer orders is never touched - the backend
 * enforces that, this dialog only says so.
 */
export function RemoveStockDialog({
  open,
  lot,
  onClose,
  onDone,
}: {
  open: boolean;
  lot: RemovableLot | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const { getAccessToken } = useAuth();
  const [mode, setMode] = useState<"all" | "some">("all");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState<string>(REMOVAL_REASONS[0]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open || !lot) return null;

  const available = Number(lot.available);
  const unit = lot.unit ?? "";
  const nothingToRemove = available <= 0;
  const invalidQuantity = mode === "some" && (!quantity || Number(quantity) <= 0 || Number(quantity) > available);

  const close = () => {
    setMode("all");
    setQuantity("");
    setError(null);
    onClose();
  };

  const handleConfirm = async () => {
    const token = getAccessToken();
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      await removeStock(token, lot.id, { ...(mode === "some" ? { quantity } : {}), reason });
      close();
      onDone();
    } catch (err) {
      setError(err instanceof InventoryApiError ? err.message : "Unable to remove stock.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={close}>
      <div className="w-full max-w-sm rounded bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-1 font-display text-lg font-semibold text-primary-900">Remove stock</h2>
        <p className="mb-4 text-sm text-neutral-500">
          {lot.product_name} · {lot.variant_name}
          <br />
          Available to remove: <strong className="text-neutral-800">{available} {unit}</strong>
          <span className="block text-xs text-neutral-400">Stock reserved for customer orders can&apos;t be removed.</span>
        </p>

        {nothingToRemove ? (
          <p className="mb-3 rounded border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm text-neutral-600">
            There&apos;s no available stock in this lot.
          </p>
        ) : (
          <>
            <div className="mb-3 flex gap-2">
              <button
                onClick={() => setMode("all")}
                className={`flex-1 rounded border px-2 py-1.5 text-xs font-semibold ${mode === "all" ? "border-status-danger bg-status-dangerLight text-status-danger" : "border-neutral-300 text-neutral-600"}`}
              >
                Remove all ({available})
              </button>
              <button
                onClick={() => setMode("some")}
                className={`flex-1 rounded border px-2 py-1.5 text-xs font-semibold ${mode === "some" ? "border-primary-700 bg-primary-800 text-white" : "border-neutral-300 text-neutral-600"}`}
              >
                Remove some
              </button>
            </div>

            {mode === "some" && (
              <input
                type="number"
                min="0"
                step="any"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder={`Quantity (max ${available})`}
                className="mb-3 w-full rounded border border-neutral-300 px-3 py-2 text-sm"
                autoFocus
              />
            )}

            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">Reason</label>
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="mb-3 w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm"
            >
              {REMOVAL_REASONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </>
        )}

        {error && (
          <p className="mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>
        )}

        <div className="flex justify-end gap-2">
          <button onClick={close} className="rounded border border-neutral-300 px-4 py-2 text-sm">
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={saving || nothingToRemove || invalidQuantity}
            className="rounded bg-status-danger px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {saving ? "Removing..." : mode === "all" ? "Remove all stock" : "Remove stock"}
          </button>
        </div>
      </div>
    </div>
  );
}
