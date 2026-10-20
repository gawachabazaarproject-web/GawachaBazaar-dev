"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  amountToPacks,
  amountUnits,
  fetchLocations,
  InventoryApiError,
  Location,
  packCount,
  packSize,
  packTotal,
  receiveStock,
} from "@/lib/inventory";
import { ProductVariant } from "@/lib/products";
import { BusyLabel } from "@/components/Spinner";
import { SearchableSelect } from "@/components/SearchableSelect";

interface Row {
  quantity: string;
  unit: string; // "" = the size's first weight/volume unit, "PACKS" = a number of packs
}

/**
 * Add stock to several sizes of one product in one go: pick the warehouse,
 * type what arrived for each size (empty sizes are skipped), check the
 * review box, then save. All sizes of one delivery share a single batch.
 */
export function ReceiveStockForm({
  variants,
  onReceived,
  onCancel,
}: {
  variants: ProductVariant[];
  onReceived: () => void;
  onCancel?: () => void;
}) {
  const { getAccessToken } = useAuth();
  const [rows, setRows] = useState<Record<number, Row>>({});
  const [locations, setLocations] = useState<Location[]>([]);
  const [locationId, setLocationId] = useState("");
  const [remarks, setRemarks] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (token) fetchLocations(token).then(setLocations).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A different product (or a refreshed size list) starts a clean form.
  const variantKey = variants.map((v) => v.id).join(",");
  useEffect(() => {
    setRows({});
  }, [variantKey]);

  const entryUnit = (v: ProductVariant) => {
    const chosen = rows[v.id]?.unit;
    const units = amountUnits(v.unit);
    return chosen && (chosen === "PACKS" || units.some((u) => u.value === chosen)) ? chosen : units[0]?.value ?? "PACKS";
  };
  const setRow = (id: number, patch: Partial<Row>) =>
    setRows((cur) => ({ ...cur, [id]: { ...(cur[id] ?? { quantity: "", unit: "" }), ...patch } }));

  const filled = variants.filter((v) => Number(rows[v.id]?.quantity) > 0);
  const packsOf = (v: ProductVariant) => {
    const unit = entryUnit(v);
    const qty = rows[v.id]?.quantity ?? "";
    return unit === "PACKS" ? Number(qty) : amountToPacks(qty || 0, unit, v.quantity, v.unit);
  };
  const locationName = locations.find((l) => String(l.id) === locationId)?.name;

  const handleSubmit = async () => {
    const token = getAccessToken();
    if (!token || !locationId || filled.length === 0) return;
    setSaving(true);
    setError(null);
    setSaved(null);
    let batchId: number | undefined;
    const done: string[] = [];
    try {
      for (const v of filled) {
        const unit = entryUnit(v);
        const quantity = rows[v.id].quantity;
        const lot = await receiveStock(token, {
          ...(batchId ? { batch_id: batchId } : {}),
          variant_id: v.id,
          location_id: Number(locationId),
          ...(unit !== "PACKS" ? { amount: quantity, amount_unit: unit } : { quantity }),
          remarks: remarks || undefined,
        });
        batchId = lot.batch_id;
        done.push(v.name);
        setRows((cur) => {
          const next = { ...cur };
          delete next[v.id]; // keep only what still has to be saved if a later size fails
          return next;
        });
      }
      setRemarks("");
      setSaved(`Stock saved for ${done.join(", ")}.`);
      onReceived();
    } catch (err) {
      const msg = err instanceof InventoryApiError ? err.message : "Unable to receive stock.";
      setError(done.length > 0 ? `Saved ${done.join(", ")}. Then: ${msg}` : msg);
      if (done.length > 0) onReceived();
    } finally {
      setSaving(false);
    }
  };

  if (variants.length === 0) return <p className="text-sm text-neutral-400">This product has no sizes yet. Add a size first.</p>;

  return (
    <div>
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">Warehouse</label>
      <SearchableSelect
        className="mb-3"
        value={locationId}
        onChange={setLocationId}
        placeholder="Choose a warehouse"
        options={locations.map((l) => ({ value: String(l.id), label: l.name }))}
      />

      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">
        What arrived (fill in the sizes you received)
      </label>
      <div className="space-y-2">
        {variants.map((v) => {
          const units = amountUnits(v.unit);
          const unit = entryUnit(v);
          const qty = rows[v.id]?.quantity ?? "";
          return (
            <div key={v.id} className="flex items-center gap-2 rounded border border-neutral-200 p-2">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-neutral-800">{v.name}</p>
                <p className="text-xs text-neutral-400">{v.sku} · pack of {packSize(v.quantity, v.unit)}</p>
              </div>
              <input
                type="number"
                min="0"
                step="any"
                value={qty}
                onChange={(e) => setRow(v.id, { quantity: e.target.value })}
                placeholder="0"
                aria-label={`${v.name} quantity received`}
                className="w-24 rounded border border-neutral-300 px-2 py-1.5 text-right text-sm"
              />
              <select
                value={unit}
                onChange={(e) => setRow(v.id, { unit: e.target.value })}
                aria-label={`${v.name} unit`}
                className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm"
              >
                {units.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
                <option value="PACKS">packs</option>
              </select>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-xs text-neutral-400">
        Sizes of one product share the same stock, so receiving the same physical stock under two sizes counts twice.
      </p>

      <label className="mb-1 mt-3 block text-xs font-semibold uppercase tracking-wide text-neutral-500">Notes</label>
      <input
        value={remarks}
        onChange={(e) => setRemarks(e.target.value)}
        placeholder="e.g. receiving reference, source"
        className="mb-3 w-full rounded border border-neutral-300 px-3 py-2 text-sm"
      />

      {filled.length > 0 && (
        <div className="mb-3 rounded border border-primary-200 bg-primary-50/40 p-3 text-sm">
          <p className="mb-1 font-semibold text-primary-900">Review before saving{locationName ? ` - into ${locationName}` : ""}</p>
          <ul className="space-y-0.5 text-neutral-700">
            {filled.map((v) => (
              <li key={v.id}>
                {v.name}: {packCount(packsOf(v))} of {packSize(v.quantity, v.unit)}
                {packTotal(packsOf(v), v.quantity, v.unit) ? ` = ${packTotal(packsOf(v), v.quantity, v.unit)}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && <p className="mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>}
      {saved && <p className="mb-3 rounded border border-primary-200 bg-primary-50 px-3 py-2 text-sm text-primary-900">{saved}</p>}

      <div className="flex justify-end gap-2">
        {onCancel && (
          <button onClick={onCancel} className="rounded border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700">
            Close
          </button>
        )}
        <button
          onClick={handleSubmit}
          disabled={saving || !locationId || filled.length === 0}
          className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
        >
          {saving ? <BusyLabel>Saving...</BusyLabel> : filled.length > 1 ? `Save stock for ${filled.length} sizes` : "Save stock"}
        </button>
      </div>
    </div>
  );
}
