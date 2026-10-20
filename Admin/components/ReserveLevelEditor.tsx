"use client";

import React, { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { CatalogApiError, updateVariant } from "@/lib/products";

// Units a reserve can be typed in, per unit family: [label, factor to the family's base unit].
const FAMILIES: Record<string, { family: string; factor: number }> = {
  KG: { family: "MASS", factor: 1000 }, G: { family: "MASS", factor: 1 },
  L: { family: "VOLUME", factor: 1000 }, ML: { family: "VOLUME", factor: 1 },
  UNIT: { family: "COUNT", factor: 1 }, DOZEN: { family: "COUNT", factor: 12 },
};
const CHOICES: Record<string, { value: string; label: string }[]> = {
  MASS: [{ value: "KG", label: "kg" }, { value: "G", label: "g" }],
  VOLUME: [{ value: "L", label: "litres" }, { value: "ML", label: "ml" }],
  COUNT: [{ value: "UNIT", label: "pieces" }, { value: "DOZEN", label: "dozen" }],
};
const fmt = (n: number) => String(Number(n.toFixed(3)));

/**
 * "How much do we want to keep in reserve?" for one product variant. When
 * available stock is at or below this (or close to it) the item shows up in
 * the Overview's Low stock card and the header alerts. Leave it empty to use
 * the default reserve.
 */
export function ReserveLevelEditor({
  variantId,
  reserveLevel,
  effectiveReserve,
  variantUnit,
  variantQuantity,
  canEdit,
  onSaved,
}: {
  variantId: number;
  /** The variant's own setting (null = default). */
  reserveLevel: string | null;
  /** The reserve actually in force. */
  effectiveReserve: string | null;
  /** The variant's own size, e.g. "KG" and "0.25"; used to convert to packs. */
  variantUnit: string;
  variantQuantity: string | number;
  canEdit: boolean;
  onSaved: () => void;
}) {
  const { getAccessToken } = useAuth();
  const own = FAMILIES[variantUnit];
  const packBase = own ? Number(variantQuantity) * own.factor : 0; // one pack in base units
  const choices = own && packBase > 0 ? CHOICES[own.family] : [];
  // "PACKS" stores the number as typed; other units are converted to packs.
  const [inUnit, setInUnit] = useState("PACKS");
  const toPacks = (v: string): string =>
    inUnit === "PACKS" || v === "" ? v : fmt((Number(v) * FAMILIES[inUnit].factor) / packBase);
  const [value, setValue] = useState(reserveLevel !== null ? String(Number(reserveLevel)) : "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dirty = toPacks(value) !== (reserveLevel !== null ? String(Number(reserveLevel)) : "");

  const save = async (next: string | null) => {
    const token = getAccessToken();
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      await updateVariant(token, variantId, {
        reserve_level: next === null || next === "" ? null : toPacks(next),
      });
      if (next === null) setValue("");
      onSaved();
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to save the reserve level.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Keep in reserve</label>
      <input
        type="number"
        min="0"
        step="any"
        value={value}
        disabled={!canEdit || saving}
        onChange={(e) => setValue(e.target.value)}
        placeholder={`Default ${effectiveReserve !== null ? Number(effectiveReserve) : 10}`}
        className="w-28 rounded border border-neutral-300 px-2 py-1 text-sm disabled:bg-neutral-50"
      />
      <select
        value={inUnit}
        disabled={!canEdit || saving}
        onChange={(e) => {
          // Re-express what is typed in the newly chosen unit.
          const next = e.target.value;
          if (value !== "") {
            const packs = inUnit === "PACKS" ? Number(value) : (Number(value) * FAMILIES[inUnit].factor) / packBase;
            setValue(fmt(next === "PACKS" ? packs : (packs * packBase) / FAMILIES[next].factor));
          }
          setInUnit(next);
        }}
        className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs"
        aria-label="Reserve unit"
      >
        <option value="PACKS">packs</option>
        {choices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
      </select>
      {inUnit !== "PACKS" && value !== "" && (
        <span className="text-xs text-neutral-400">= {fmt(Number(toPacks(value)))} packs</span>
      )}
      {canEdit && dirty && (
        <button
          onClick={() => save(value)}
          disabled={saving}
          className="rounded bg-primary-800 px-2.5 py-1 text-xs font-semibold text-white disabled:opacity-40"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      )}
      {canEdit && reserveLevel !== null && !dirty && (
        <button onClick={() => save(null)} disabled={saving} className="text-xs font-semibold text-neutral-500 hover:underline">
          Use default
        </button>
      )}
      {error && <span className="text-xs text-status-danger">{error}</span>}
    </div>
  );
}
