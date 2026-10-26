"use client";

import React, { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { CatalogApiError, ProductVariant, updateVariant } from "@/lib/products";

// pack unit -> [family, size of one unit in the family's base unit (g / ml / pieces)]
const FAMILY: Record<string, [string, number]> = {
  KG: ["MASS", 1000], G: ["MASS", 1], L: ["VOLUME", 1000], ML: ["VOLUME", 1],
  UNIT: ["COUNT", 1], DOZEN: ["COUNT", 12],
};
const UNITS: Record<string, { value: string; label: string; factor: number }[]> = {
  MASS: [{ value: "KG", label: "kg", factor: 1000 }, { value: "G", label: "g", factor: 1 }],
  VOLUME: [{ value: "L", label: "L", factor: 1000 }, { value: "ML", label: "ml", factor: 1 }],
  COUNT: [{ value: "UNIT", label: "pieces", factor: 1 }, { value: "DOZEN", label: "dozen", factor: 12 }],
};
const fmt = (n: number) => String(Number(n.toFixed(3)));

/**
 * One low-stock alert for the whole product, in kg / L / pieces ("tell me
 * when tomatoes are down to 10 kg"). It is stored the way the backend keeps it,
 * as a number of packs on every size of that unit family, so each size
 * alerts at the same real amount.
 */
export function ProductAlertEditor({
  variants,
  reserves,
  canEdit,
  onSaved,
}: {
  variants: ProductVariant[];
  /** Each size's own alert in packs (null = default), by variant id. */
  reserves: Record<number, string | null>;
  canEdit: boolean;
  onSaved: () => void;
}) {
  const { getAccessToken } = useAuth();
  const counted = variants.filter((v) => FAMILY[v.unit]);
  const family = counted[0] ? FAMILY[counted[0].unit][0] : null;
  const sized = counted.filter((v) => FAMILY[v.unit][0] === family);
  const units = family ? UNITS[family] : [];

  // The alert in base units for each size that has its own setting.
  const baseOf = (v: ProductVariant, reserve: string) => Number(reserve) * Number(v.quantity) * FAMILY[v.unit][1];
  const own = sized.filter((v) => reserves[v.id] != null);
  const reserveOf = (v: ProductVariant) => reserves[v.id] as string;
  const bases = own.map((v) => baseOf(v, reserveOf(v)));
  const consistent = own.length === sized.length && bases.length > 0 && bases.every((b) => Math.abs(b - bases[0]) < 0.01);

  const [unit, setUnit] = useState(units[0]?.value ?? "");
  const factor = units.find((u) => u.value === unit)?.factor ?? 1;
  const current = consistent ? fmt(bases[0] / factor) : "";
  const [value, setValue] = useState(current);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!family || sized.length === 0) return null;
  const dirty = value !== current;

  const save = async (clear: boolean) => {
    const token = getAccessToken();
    if (!token) return;
    const amountBase = Number(value) * factor;
    if (!clear && !(amountBase >= 0)) return;
    setSaving(true);
    setError(null);
    try {
      for (const v of sized) {
        const packBase = Number(v.quantity) * FAMILY[v.unit][1];
        await updateVariant(token, v.id, { reserve_level: clear || value === "" ? null : fmt(amountBase / packBase) });
      }
      if (clear) setValue("");
      onSaved();
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to save the alert.");
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
          const next = units.find((u) => u.value === e.target.value);
          if (next && value !== "") setValue(fmt((Number(value) * factor) / next.factor));
          setUnit(e.target.value);
        }}
        aria-label="Alert unit"
        className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs"
      >
        {units.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
      </select>
      {canEdit && dirty && (
        <button onClick={() => save(false)} disabled={saving} className="rounded bg-primary-800 px-2.5 py-1 text-xs font-semibold text-white disabled:opacity-40">
          {saving ? "Saving..." : "Save"}
        </button>
      )}
      {canEdit && !dirty && own.length > 0 && (
        <button onClick={() => save(true)} disabled={saving} className="text-xs font-semibold text-neutral-500 hover:underline">
          Use default
        </button>
      )}
      {!consistent && own.length > 0 && !dirty && <span className="text-xs text-neutral-400">Sizes have different alerts (see Advanced)</span>}
      {own.length === 0 && !dirty && <span className="text-xs text-neutral-400">Using the default</span>}
      {error && <span className="text-xs text-status-danger">{error}</span>}
    </div>
  );
}
