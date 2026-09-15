"use client";

import React, { useState } from "react";

/**
 * Per the admin-panel destructive-action rule: a dangerous action is never
 * one click away. The backend still re-validates everything on submit
 * (see order_state.py) - this dialog only prevents an accidental click,
 * it is not itself the safety boundary.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  danger = false,
  requireReason = false,
  loading = false,
  error,
  onConfirm,
  onCancel,
  children,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  danger?: boolean;
  requireReason?: boolean;
  loading?: boolean;
  error?: string | null;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
  /** Extra form content rendered between the description and the reason
   * textarea/buttons - e.g. a price input for a price-change confirmation. */
  children?: React.ReactNode;
}) {
  const [reason, setReason] = useState("");

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-sm rounded bg-white p-6 shadow-xl">
        <h2 className="font-display text-lg font-semibold text-primary-900">{title}</h2>
        <p className="mt-2 text-sm text-neutral-600">{description}</p>

        {children}

        {requireReason && (
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason (visible to the customer)"
            rows={3}
            className="mt-3 w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
        )}

        {error && (
          <p className="mt-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">
            {error}
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={loading}
            className="rounded border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(reason)}
            disabled={loading}
            className={`rounded px-4 py-2 text-sm font-semibold text-white disabled:opacity-60 ${
              danger ? "bg-status-danger hover:bg-status-danger/90" : "bg-primary-800 hover:bg-primary-700"
            }`}
          >
            {loading ? "Working..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
