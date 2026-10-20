"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  amountToPacks,
  amountUnits,
  fetchLocations,
  InventoryApiError,
  Location,
  packCount,
  packSize,
  receiveStock,
  setStockShares,
} from "@/lib/inventory";
import { ProductVariant } from "@/lib/products";
import { SearchableSelect } from "@/components/SearchableSelect";
import { BusyLabel } from "@/components/Spinner";

// pack unit -> unit family
const FAMILY: Record<string, string> = { KG: "MASS", G: "MASS", L: "VOLUME", ML: "VOLUME", UNIT: "COUNT", DOZEN: "COUNT" };
const trim = (n: number) => String(Number(n.toFixed(3)));

/**
 * Receive stock for one product.
 *
 * 1. Type the TOTAL that arrived (e.g. 100 kg) and the warehouse.
 * 2. Optionally divide it between the sizes ("1 kg: 40 kg, 500 g: 30 kg").
 *    Whatever is not assigned stays in inventory as unassigned stock, shared
 *    by all sizes, until you assign it.
 *
 * Sizes that are not weight/volume/count based (boxes, packs) are received as
 * a number of packs. Everything of one delivery shares one batch.
 */
export function ReceiveStockForm({
  productId,
  variants,
  onReceived,
  onCancel,
  emptyHint = "This product has no sizes yet. Add a size first.",
}: {
  productId: number;
  variants: ProductVariant[];
  onReceived: () => void;
  onCancel?: () => void;
  /** Shown while there are no sizes to fill in. */
  emptyHint?: string;
}) {
  const { getAccessToken, user } = useAuth();
  const canAssign = !!(user && hasPermission(user.roles, "inventory.adjust"));

  // The unit family the total is entered in: the one with the most sizes.
  const counts: Record<string, number> = {};
  for (const v of variants) if (FAMILY[v.unit]) counts[FAMILY[v.unit]] = (counts[FAMILY[v.unit]] ?? 0) + 1;
  const family = Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0] ?? null;
  const familyVariants = variants.filter((v) => family && FAMILY[v.unit] === family);
  const otherVariants = variants.filter((v) => !familyVariants.includes(v));
  const units = familyVariants[0] ? amountUnits(familyVariants[0].unit) : [];

  const [locations, setLocations] = useState<Location[]>([]);
  const [locationId, setLocationId] = useState("");
  const [total, setTotal] = useState("");
  const [totalUnit, setTotalUnit] = useState("");
  const [assigned, setAssigned] = useState<Record<number, string>>({});
  const [packsOther, setPacksOther] = useState<Record<number, string>>({});
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
    setTotal("");
    setTotalUnit("");
    setAssigned({});
    setPacksOther({});
  }, [variantKey]);

  const unit = totalUnit && units.some((u) => u.value === totalUnit) ? totalUnit : units[0]?.value ?? "";
  const unitLabel = units.find((u) => u.value === unit)?.label ?? "";
  const totalNum = Number(total) > 0 ? Number(total) : 0;
  const assignedNum = (id: number) => (Number(assigned[id]) > 0 ? Number(assigned[id]) : 0);
  const assignedSum = familyVariants.reduce((sum, v) => sum + assignedNum(v.id), 0);
  const unassigned = totalNum - assignedSum;
  const overAssigned = unassigned < -0.0005;
  const otherFilled = otherVariants.filter((v) => Number(packsOther[v.id]) > 0);
  const nothingToSave = totalNum <= 0 && otherFilled.length === 0;

  const packsFor = (v: ProductVariant, amount: number) => Math.floor(amountToPacks(amount, unit, v.quantity, v.unit));
  const locationName = locations.find((l) => String(l.id) === locationId)?.name;

  const handleSubmit = async () => {
    const token = getAccessToken();
    if (!token || !locationId || nothingToSave || overAssigned) return;
    setSaving(true);
    setError(null);
    setSaved(null);
    let batchId: number | undefined;
    const done: string[] = [];
    try {
      // 1) The total goes into the product's shared stock, against its first size.
      if (totalNum > 0 && familyVariants[0]) {
        const lot = await receiveStock(token, {
          variant_id: familyVariants[0].id,
          location_id: Number(locationId),
          amount: String(totalNum),
          amount_unit: unit,
          remarks: remarks || undefined,
        });
        batchId = lot.batch_id;
        done.push(`${trim(totalNum)} ${unitLabel}`);
        setTotal("");
      }
      // 2) Counted sizes (boxes, packs) are received as a number of packs.
      for (const v of otherFilled) {
        const lot = await receiveStock(token, {
          ...(batchId ? { batch_id: batchId } : {}),
          variant_id: v.id,
          location_id: Number(locationId),
          quantity: packsOther[v.id],
          remarks: remarks || undefined,
        });
        batchId = lot.batch_id;
        done.push(`${packsOther[v.id]} packs of ${v.name}`);
        setPacksOther((cur) => {
          const next = { ...cur };
          delete next[v.id];
          return next;
        });
      }
      onReceived();
      // 3) Hand out the shares; the rest stays unassigned in inventory.
      const shares = familyVariants
        .filter((v) => assignedNum(v.id) > 0)
        .map((v) => ({ variant_id: v.id, amount: String(assignedNum(v.id)), amount_unit: unit }));
      if (shares.length > 0) {
        try {
          await setStockShares(token, productId, shares, true);
        } catch (err) {
          const msg = err instanceof InventoryApiError ? err.message : "Unable to assign the stock.";
          setError(`Stock received (${done.join(", ")}), but dividing it failed: ${msg} You can assign it from Inventory → By product.`);
          setAssigned({});
          return;
        }
        onReceived();
      }
      const left = unassigned > 0.0005 ? `${trim(unassigned)} ${unitLabel} left unassigned in inventory.` : "";
      setSaved(
        `Received ${done.join(", ")}.` + (assignedSum > 0 ? ` ${trim(assignedSum)} ${unitLabel} assigned to sizes.` : "") + (left ? ` ${left}` : ""),
      );
      setAssigned({});
      setRemarks("");
    } catch (err) {
      const msg = err instanceof InventoryApiError ? err.message : "Unable to receive stock.";
      setError(done.length > 0 ? `Received ${done.join(", ")}. Then: ${msg}` : msg);
      if (done.length > 0) onReceived();
    } finally {
      setSaving(false);
    }
  };

  const label = "mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500";

  return (
    <div>
      <label className={label}>Warehouse</label>
      <SearchableSelect
        className="mb-3"
        value={locationId}
        onChange={setLocationId}
        placeholder="Choose a warehouse"
        options={locations.map((l) => ({ value: String(l.id), label: l.name }))}
      />

      {variants.length === 0 && (
        <>
          <label className={label}>Total received</label>
          <p className="mb-3 rounded border border-dashed border-neutral-300 px-3 py-4 text-center text-[13px] text-neutral-400">{emptyHint}</p>
        </>
      )}

      {family && familyVariants.length > 0 && (
        <>
          <label className={label}>Total received</label>
          <div className="mb-1 flex gap-2">
            <input
              type="number"
              min="0"
              step="any"
              value={total}
              onChange={(e) => setTotal(e.target.value)}
              placeholder="e.g. 100"
              aria-label="Total received"
              className="w-full rounded border border-neutral-300 px-3 py-1.5 text-[13px] focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
            <select
              value={unit}
              onChange={(e) => setTotalUnit(e.target.value)}
              aria-label="Unit"
              className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-[13px]"
            >
              {units.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
            </select>
          </div>
          <p className="mb-3 text-xs text-neutral-400">
            The whole amount goes into this product&apos;s stock. Divide it between sizes below, or leave it unassigned - it stays in
            inventory, shared by all sizes.
          </p>

          {canAssign && familyVariants.length > 1 && (
            <>
              <div className="mb-1 flex items-end justify-between">
                <label className="block text-xs font-semibold uppercase tracking-wide text-neutral-500">Divide between sizes (optional)</label>
                <span className={`text-xs font-semibold ${overAssigned ? "text-status-danger" : "text-primary-800"}`}>
                  {totalNum <= 0 ? "" : overAssigned ? `${trim(-unassigned)} ${unitLabel} too much` : `Unassigned: ${trim(unassigned)} ${unitLabel}`}
                </span>
              </div>
              <div className="space-y-2">
                {familyVariants.map((v) => {
                  const amount = assignedNum(v.id);
                  return (
                    <div key={v.id} className="flex items-center gap-2 rounded border border-neutral-200 p-2">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] font-medium text-neutral-800">{v.name}</p>
                        <p className="text-xs text-neutral-400">
                          {v.sku} · pack of {packSize(v.quantity, v.unit)}
                          {amount > 0 && <span className="text-neutral-500"> · = {packCount(packsFor(v, amount))}</span>}
                        </p>
                      </div>
                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={assigned[v.id] ?? ""}
                        onChange={(e) => setAssigned((cur) => ({ ...cur, [v.id]: e.target.value }))}
                        placeholder="0"
                        aria-label={`${v.name} share in ${unitLabel}`}
                        className="w-24 rounded border border-neutral-300 px-2 py-1.5 text-right text-[13px]"
                      />
                      <span className="w-12 text-xs text-neutral-500">{unitLabel}</span>
                      <button
                        type="button"
                        disabled={unassigned <= 0.0005}
                        onClick={() => setAssigned((cur) => ({ ...cur, [v.id]: trim(assignedNum(v.id) + unassigned) }))}
                        className="text-xs font-semibold text-primary-700 hover:underline disabled:text-neutral-300 disabled:no-underline"
                        title="Put everything not yet assigned here"
                      >
                        Rest
                      </button>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}

      {otherVariants.length > 0 && (
        <>
          <label className={`${label} mt-3`}>Counted sizes (boxes, packs)</label>
          <div className="space-y-2">
            {otherVariants.map((v) => (
              <div key={v.id} className="flex items-center gap-2 rounded border border-neutral-200 p-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-medium text-neutral-800">{v.name}</p>
                  <p className="text-xs text-neutral-400">{v.sku} · pack of {packSize(v.quantity, v.unit)}</p>
                </div>
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={packsOther[v.id] ?? ""}
                  onChange={(e) => setPacksOther((cur) => ({ ...cur, [v.id]: e.target.value }))}
                  placeholder="0"
                  aria-label={`${v.name} packs received`}
                  className="w-24 rounded border border-neutral-300 px-2 py-1.5 text-right text-[13px]"
                />
                <span className="w-12 text-xs text-neutral-500">packs</span>
              </div>
            ))}
          </div>
        </>
      )}

      <label className={`${label} mt-3`}>Notes</label>
      <input
        value={remarks}
        onChange={(e) => setRemarks(e.target.value)}
        placeholder="e.g. receiving reference, source"
        className="mb-3 w-full rounded border border-neutral-300 px-3 py-1.5 text-[13px]"
      />

      {!nothingToSave && (
        <div className="mb-3 rounded border border-primary-200 bg-primary-50/40 p-3 text-[13px]">
          <p className="mb-1 font-semibold text-primary-900">Review before saving{locationName ? ` - into ${locationName}` : ""}</p>
          <ul className="space-y-0.5 text-neutral-700">
            {totalNum > 0 && (
              <li>
                Receive <strong>{trim(totalNum)} {unitLabel}</strong>
                {assignedSum > 0 ? ` - ${trim(assignedSum)} ${unitLabel} assigned to sizes` : " - all unassigned"}
                {unassigned > 0.0005 && assignedSum > 0 ? `, ${trim(unassigned)} ${unitLabel} stays unassigned` : ""}
              </li>
            )}
            {familyVariants
              .filter((v) => assignedNum(v.id) > 0)
              .map((v) => (
                <li key={v.id} className="pl-3 text-neutral-600">
                  {v.name}: {trim(assignedNum(v.id))} {unitLabel} = {packCount(packsFor(v, assignedNum(v.id)))}
                </li>
              ))}
            {otherFilled.map((v) => (
              <li key={v.id}>{v.name}: {packCount(packsOther[v.id])}</li>
            ))}
          </ul>
        </div>
      )}

      {error && <p className="mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-[13px] text-status-danger">{error}</p>}
      {saved && <p className="mb-3 rounded border border-primary-200 bg-primary-50 px-3 py-2 text-[13px] text-primary-900">{saved}</p>}

      <div className="flex justify-end gap-2">
        {onCancel && (
          <button onClick={onCancel} className="rounded border border-neutral-300 px-3.5 py-1.5 text-[13px] font-medium text-neutral-700">
            Close
          </button>
        )}
        <button
          onClick={handleSubmit}
          disabled={saving || !locationId || nothingToSave || overAssigned}
          className="rounded bg-primary-800 px-3.5 py-1.5 text-[13px] font-semibold text-white disabled:opacity-40"
        >
          {saving ? <BusyLabel>Saving...</BusyLabel> : "Save stock"}
        </button>
      </div>
    </div>
  );
}
