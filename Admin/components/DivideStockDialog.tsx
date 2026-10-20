"use client";

import React, { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  divideProductStock,
  InventoryApiError,
  packCount,
  packSize,
  ProductStockItem,
  shareProductStock,
} from "@/lib/inventory";

// unit -> [family, size of one unit in the family's base unit]
const FAMILY: Record<string, [string, number]> = {
  KG: ["MASS", 1000], G: ["MASS", 1], L: ["VOLUME", 1000], ML: ["VOLUME", 1], UNIT: ["COUNT", 1], DOZEN: ["COUNT", 12],
};
// How the shares are typed and sent, per family: [label, API unit, base units per typed unit].
const TYPED: Record<string, [string, string, number]> = {
  MASS: ["kg", "KG", 1000], VOLUME: ["L", "L", 1000], COUNT: ["pieces", "UNIT", 1],
};
const trim = (n: number) => String(Number(n.toFixed(3)));

/** Which family of this product can be divided (needs two or more sizes). */
export function dividableFamily(p: ProductStockItem): string | null {
  const counts: Record<string, number> = {};
  for (const v of p.variants) {
    const f = FAMILY[v.pack_unit]?.[0];
    if (f) counts[f] = (counts[f] ?? 0) + 1;
  }
  return Object.keys(counts).find((f) => counts[f] >= 2) ?? null;
}

/**
 * Splits a product's stock between its sizes by hand ("1 kg: 10, 500 g: 12,
 * 250 g: 12"). Each size then sells only its own share. The backend moves the
 * stock between the sizes' lots and checks that the shares add up.
 */
export function DivideStockDialog({
  product,
  onClose,
  onDone,
}: {
  product: ProductStockItem | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const { getAccessToken } = useAuth();
  const [values, setValues] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!product) return null;
  const family = dividableFamily(product);
  if (!family) return null;
  const [typedLabel, typedUnit, typedBase] = TYPED[family];
  const variants = product.variants.filter((v) => FAMILY[v.pack_unit]?.[0] === family);
  const split = variants.some((v) => v.dedicated);
  const total = variants.reduce((sum, v) => sum + Number(v.held_amount), 0);

  // Typed value for a size: what the admin entered, else what it holds now
  // when the stock is already divided.
  const valueOf = (id: number, held: string, dedicated: boolean) =>
    values[id] ?? (split && dedicated ? trim(Number(held)) : "");
  const assigned = variants.reduce((sum, v) => sum + Number(valueOf(v.variant_id, v.held_amount, v.dedicated) || 0), 0);
  const remaining = total - assigned;
  const balanced = Math.abs(remaining) < 0.0005;

  const close = () => {
    setValues({});
    setError(null);
    onClose();
  };

  const run = async (action: () => Promise<unknown>, fallback: string) => {
    setSaving(true);
    setError(null);
    try {
      await action();
      close();
      onDone();
    } catch (err) {
      setError(err instanceof InventoryApiError ? err.message : fallback);
    } finally {
      setSaving(false);
    }
  };

  const apply = () => {
    const token = getAccessToken();
    if (!token) return;
    run(
      () =>
        divideProductStock(token, product.product_id, {
          shares: variants.map((v) => ({
            variant_id: v.variant_id,
            amount: String(valueOf(v.variant_id, v.held_amount, v.dedicated) || 0),
            amount_unit: typedUnit,
          })),
        }),
      "Unable to divide the stock.",
    );
  };

  const shareAgain = () => {
    const token = getAccessToken();
    if (!token) return;
    run(() => shareProductStock(token, product.product_id, variants[0].variant_id), "Unable to share the stock.");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={close}>
      <div className="w-full max-w-md rounded bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-1 font-display text-lg font-semibold text-primary-900">Divide stock</h2>
        <p className="mb-4 text-sm text-neutral-500">
          {product.product_name} · <strong className="text-neutral-800">{trim(total)} {typedLabel}</strong> to divide.
          Each size will sell only its own share.
        </p>

        <div className="space-y-2">
          {variants.map((v) => {
            const raw = valueOf(v.variant_id, v.held_amount, v.dedicated);
            const size = Number(v.pack_quantity) * FAMILY[v.pack_unit][1];
            const packs = Math.floor(((Number(raw) || 0) * typedBase) / size + 1e-9);
            return (
              <div key={v.variant_id} className="flex items-center gap-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-neutral-800">{v.variant_name}</p>
                  <p className="text-xs text-neutral-400">pack of {packSize(v.pack_quantity, v.pack_unit)} · {packCount(packs)}</p>
                </div>
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={raw}
                  onChange={(e) => setValues((cur) => ({ ...cur, [v.variant_id]: e.target.value }))}
                  placeholder="0"
                  aria-label={`${v.variant_name} share in ${typedLabel}`}
                  className="w-24 rounded border border-neutral-300 px-2 py-1.5 text-right text-sm"
                />
                <span className="w-10 text-xs text-neutral-500">{typedLabel}</span>
                <button
                  type="button"
                  disabled={balanced || remaining < 0}
                  onClick={() =>
                    setValues((cur) => ({ ...cur, [v.variant_id]: trim((Number(raw) || 0) + remaining) }))
                  }
                  className="text-xs font-semibold text-primary-700 hover:underline disabled:text-neutral-300 disabled:no-underline"
                  title="Put everything not yet assigned here"
                >
                  Rest
                </button>
              </div>
            );
          })}
        </div>

        <p className={`mt-3 text-sm ${balanced ? "text-primary-800" : "text-status-warning"}`}>
          {balanced
            ? "All stock is assigned."
            : remaining > 0
              ? `${trim(remaining)} ${typedLabel} still to assign.`
              : `${trim(-remaining)} ${typedLabel} too much.`}
        </p>
        <p className="mt-1 text-xs text-neutral-400">
          Only stock that is free is moved; anything already reserved for customer orders stays where it is.
          Whole packs only are sold, so a share that is not a multiple of the pack size keeps a small leftover.
        </p>

        {error && (
          <p className="mt-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>
        )}

        <div className="mt-4 flex items-center justify-between gap-2">
          {split ? (
            <button onClick={shareAgain} disabled={saving} className="text-sm font-semibold text-neutral-600 hover:underline">
              Share stock again
            </button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <button onClick={close} className="rounded border border-neutral-300 px-3 py-1.5 text-sm font-semibold text-neutral-700">
              Cancel
            </button>
            <button
              onClick={apply}
              disabled={saving || !balanced || total <= 0}
              className="rounded bg-primary-800 px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-40"
            >
              {saving ? "Dividing..." : "Divide stock"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
