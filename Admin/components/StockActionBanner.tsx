"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { InventoryApiError, ProductStockOperation, stockErrorMessage, undoStockAction } from "@/lib/inventory";

export interface StockNotice {
  /** What happened, e.g. "Removed 2 kg of Tomato". */
  message: string;
  /** Set for correct / remove / move, which can be undone for a while. */
  operation?: ProductStockOperation;
}

/**
 * "✓ Removed 2 kg of Tomato  [Undo]". Undo is a compensating action done by the
 * server, which refuses when the stock has since been used - then this says so
 * plainly and points to the history instead of pretending.
 */
export function StockActionBanner({
  notice,
  onChanged,
  onDismiss,
  historyHref,
}: {
  notice: StockNotice;
  /** Called after an undo so the screen can refresh its numbers. */
  onChanged: (op?: ProductStockOperation) => void;
  onDismiss: () => void;
  historyHref: string;
}) {
  const { getAccessToken } = useAuth();
  const op = notice.operation;
  const deadline = op?.undo_until ? new Date(op.undo_until).getTime() : 0;
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [undone, setUndone] = useState(false);
  const [problem, setProblem] = useState<{ text: string; cannotUndo: boolean } | null>(null);

  useEffect(() => {
    if (!deadline) return;
    const timer = window.setInterval(() => setNow(Date.now()), 15_000);
    return () => window.clearInterval(timer);
  }, [deadline]);

  // A fresh notice starts clean.
  useEffect(() => {
    setUndone(false);
    setProblem(null);
    setBusy(false);
  }, [notice]);

  const canUndo = !!op?.operation_id && deadline > now && !undone;

  const undo = async () => {
    const token = getAccessToken();
    if (!token || !op?.operation_id) return;
    setBusy(true);
    setProblem(null);
    try {
      const result = await undoStockAction(token, op.operation_id);
      setUndone(true);
      onChanged(result);
    } catch (err) {
      if (err instanceof InventoryApiError && err.status === 409) {
        setProblem({ text: "This can no longer be undone automatically.", cannotUndo: true });
      } else {
        setProblem({ text: stockErrorMessage(err, "undo that"), cannotUndo: false });
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div role="status" aria-live="polite" className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-1 rounded border border-primary-200 bg-primary-50 px-4 py-2.5 text-sm text-primary-900">
      <span>{undone ? "✓ Undone. The stock is back as it was." : `✓ ${notice.message}`}</span>
      {canUndo && !problem && (
        <button type="button" onClick={undo} disabled={busy} className="font-semibold underline disabled:opacity-50">
          {busy ? "Undoing..." : "Undo"}
        </button>
      )}
      {problem && (
        <span className="text-status-danger">
          {problem.text}{" "}
          {problem.cannotUndo ? (
            <Link href={historyHref} className="font-semibold underline">View history</Link>
          ) : (
            <button type="button" onClick={undo} className="font-semibold underline">Try again</button>
          )}
        </span>
      )}
      <button type="button" onClick={onDismiss} aria-label="Dismiss" className="ml-auto text-neutral-500 hover:text-neutral-800">×</button>
    </div>
  );
}
