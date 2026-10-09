"use client";

import React, { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { CatalogApiError, updateVariant } from "@/lib/products";

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
  unit,
  canEdit,
  onSaved,
}: {
  variantId: number;
  /** The variant's own setting (null = default). */
  reserveLevel: string | null;
  /** The reserve actually in force. */
  effectiveReserve: string | null;
  unit: string;
  canEdit: boolean;
  onSaved: () => void;
}) {
  const { getAccessToken } = useAuth();
  const [value, setValue] = useState(reserveLevel !== null ? String(Number(reserveLevel)) : "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dirty = value !== (reserveLevel !== null ? String(Number(reserveLevel)) : "");

  const save = async (next: string | null) => {
    const token = getAccessToken();
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      await updateVariant(token, variantId, { reserve_level: next === null || next === "" ? null : next });
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
      <span className="text-xs text-neutral-500">{unit}</span>
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
