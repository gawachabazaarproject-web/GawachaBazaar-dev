"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { CatalogApiError, ProductVariant } from "@/lib/products";
import {
  clearProductReserve,
  fetchProductStockCard,
  InventoryApiError,
  setProductReserve,
  type ProductStockTotal,
} from "@/lib/inventory";
import { AMOUNT_UNITS_BY_DIMENSION, UNITS, convert, dimensionOf } from "@/lib/units";

const fmt = (n: number) => String(Number(n.toFixed(3)));

/**
 * One low-stock alert for the whole product, as ONE physical amount ("tell me
 * when tomatoes are down to 10 kg"). The server stores it in grams / ml / pieces
 * and judges every size against that same amount, so 5 kg is 20 x 250 g, 10 x
 * 500 g or 5 x 1 kg. Without it the older per-size levels (below) still apply.
 */
export function ProductAlertEditor({
  productId,
  variants,
  canEdit,
  onSaved,
}: {
  productId: number;
  variants: ProductVariant[];
  canEdit: boolean;
  onSaved: () => void;
}) {
  const { getAccessToken } = useAuth();
  const family = variants.map((v) => dimensionOf(v.unit)).find((d) => d === "MASS" || d === "VOLUME" || d === "COUNT") ?? null;
  const unitValues = family ? AMOUNT_UNITS_BY_DIMENSION[family] : [];
  const [unit, setUnit] = useState(unitValues[0] ?? "");
  const [stored, setStored] = useState<ProductStockTotal | null>(null);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token || !family) return;
    try {
      const card = await fetchProductStockCard(token, productId);
      const total = card.totals.find((t) => t.family === family) ?? null;
      setStored(total);
      // The server reports the reserve in kg / L / pcs; show it in the chosen unit.
      const shownUnit = unitValues[0];
      const reserve = total?.reserve_amount != null ? Number(total.reserve_amount) : null;
      setValue(reserve === null ? "" : fmt(convert(reserve, shownUnit, unit) ?? reserve));
    } catch {
      setStored(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId, family, getAccessToken]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!family || unitValues.length === 0) return null;
  const has = stored?.reserve_amount != null;
  const serverValue = has ? fmt(convert(Number(stored!.reserve_amount), unitValues[0], unit) ?? 0) : "";
  const dirty = value !== serverValue;

  const run = async (clear: boolean) => {
    const token = getAccessToken();
    if (!token) return;
    if (!clear && !(Number(value) >= 0 && value !== "")) return;
    setSaving(true);
    setError(null);
    try {
      if (clear) await clearProductReserve(token, productId);
      else await setProductReserve(token, productId, { amount: value, amount_unit: unit });
      await load();
      onSaved();
    } catch (err) {
      setError(err instanceof InventoryApiError || err instanceof CatalogApiError ? err.message : "Unable to save the alert.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Low-stock alert</label>
      <input
        type="number"
        min="0"
        step="any"
        value={value}
        disabled={!canEdit || saving}
        onChange={(e) => setValue(e.target.value)}
        placeholder="e.g. 10"
        aria-label="Low-stock alert amount"
        className="w-24 rounded border border-neutral-300 px-2 py-1 text-sm disabled:bg-neutral-50"
      />
      <select
        value={unit}
        disabled={!canEdit || saving}
        onChange={(e) => {
          const next = e.target.value;
          if (value !== "") setValue(fmt(convert(Number(value), unit, next) ?? Number(value)));
          setUnit(next);
        }}
        aria-label="Alert unit"
        className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs"
      >
        {unitValues.map((u) => <option key={u} value={u}>{UNITS[u].inputLabel}</option>)}
      </select>
      {canEdit && dirty && value !== "" && (
        <button onClick={() => run(false)} disabled={saving} className="rounded bg-primary-800 px-2.5 py-1 text-xs font-semibold text-white disabled:opacity-40">
          {saving ? "Saving..." : "Save"}
        </button>
      )}
      {canEdit && !dirty && has && (
        <button onClick={() => run(true)} disabled={saving} className="text-xs font-semibold text-neutral-500 hover:underline">
          Use the per-size levels
        </button>
      )}
      {!has && !dirty && <span className="text-xs text-neutral-400">Using the per-size levels below</span>}
      {error && <span className="text-xs text-status-danger">{error}</span>}
    </div>
  );
}
