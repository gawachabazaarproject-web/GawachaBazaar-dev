"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { amountToPacks, amountUnits, fetchLocations, InventoryApiError, Location, packCount, packSize, receiveStock } from "@/lib/inventory";
import { fetchAdminProducts, fetchAdminProductDetail, AdminProductListItem, ProductVariant } from "@/lib/products";
import { BusyLabel } from "@/components/Spinner";

interface Row {
  quantity: string;
  unit: string; // "" = the variant's first weight/volume unit, "PACKS" = a number of packs
}

/**
 * Receive stock for one product: pick the product and warehouse, then type
 * what arrived for each of its sizes in the same place. Sizes left empty are
 * skipped. All sizes of one delivery share a single batch.
 */
export function ReceiveStockDialog({
  open,
  onClose,
  onReceived,
  initialProductId,
}: {
  open: boolean;
  onClose: () => void;
  onReceived: () => void;
  initialProductId?: number;
}) {
  const { getAccessToken } = useAuth();

  const [products, setProducts] = useState<AdminProductListItem[]>([]);
  const [productId, setProductId] = useState("");
  const [variants, setVariants] = useState<ProductVariant[]>([]);
  const [rows, setRows] = useState<Record<number, Row>>({});
  const [locations, setLocations] = useState<Location[]>([]);
  const [locationId, setLocationId] = useState("");
  const [remarks, setRemarks] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const token = getAccessToken();
    if (!token) return;
    fetchAdminProducts(token, { page_size: 100 }).then((r) => setProducts(r.items)).catch(() => undefined);
    fetchLocations(token).then(setLocations).catch(() => undefined);
    if (initialProductId) setProductId(String(initialProductId));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialProductId]);

  useEffect(() => {
    setRows({});
    if (!productId) {
      setVariants([]);
      return;
    }
    const token = getAccessToken();
    if (!token) return;
    fetchAdminProductDetail(token, Number(productId)).then((p) => setVariants(p.variants)).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  if (!open) return null;

  const unitsFor = (v: ProductVariant) => amountUnits(v.unit);
  const entryUnit = (v: ProductVariant) => {
    const chosen = rows[v.id]?.unit;
    const units = unitsFor(v);
    return chosen && (chosen === "PACKS" || units.some((u) => u.value === chosen)) ? chosen : units[0]?.value ?? "PACKS";
  };
  const setRow = (id: number, patch: Partial<Row>) =>
    setRows((cur) => ({ ...cur, [id]: { ...(cur[id] ?? { quantity: "", unit: "" }), ...patch } }));

  const filled = variants.filter((v) => Number(rows[v.id]?.quantity) > 0);

  const reset = () => {
    setProductId("");
    setLocationId("");
    setRows({});
    setRemarks("");
    setError(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async () => {
    const token = getAccessToken();
    if (!token || !productId || !locationId || filled.length === 0) return;
    setSaving(true);
    setError(null);
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
        // Keep only the sizes that still have to be received if a later one fails.
        setRows((cur) => {
          const next = { ...cur };
          delete next[v.id];
          return next;
        });
      }
      handleClose();
      onReceived();
    } catch (err) {
      const msg = err instanceof InventoryApiError ? err.message : "Unable to receive stock.";
      setError(done.length > 0 ? `Received ${done.join(", ")}. Then: ${msg}` : msg);
      if (done.length > 0) onReceived();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded bg-white p-6 shadow-xl">
        <h2 className="mb-4 font-display text-lg font-semibold text-primary-900">Receive stock</h2>

        <Field label="Product">
          <select value={productId} onChange={(e) => setProductId(e.target.value)} className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm">
            <option value="">Choose a product</option>
            {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </Field>

        <Field label="Warehouse">
          <select value={locationId} onChange={(e) => setLocationId(e.target.value)} className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm">
            <option value="">Choose a warehouse</option>
            {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </Field>

        {productId && (
          <Field label="What arrived (fill in the sizes you received)">
            {variants.length === 0 ? (
              <p className="text-sm text-neutral-400">This product has no sizes yet.</p>
            ) : (
              <div className="space-y-2">
                {variants.map((v) => {
                  const units = unitsFor(v);
                  const unit = entryUnit(v);
                  const byAmount = unit !== "PACKS";
                  const qty = rows[v.id]?.quantity ?? "";
                  const packs = byAmount ? amountToPacks(qty || 0, unit, v.quantity, v.unit) : Number(qty);
                  return (
                    <div key={v.id} className="rounded border border-neutral-200 p-2">
                      <div className="flex items-center gap-2">
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
                      {Number(qty) > 0 && (
                        <p className="mt-1 text-xs text-neutral-500">
                          {byAmount ? `= ${packCount(packs)} of ${packSize(v.quantity, v.unit)}` : `${packCount(qty)} of ${packSize(v.quantity, v.unit)}`}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            <p className="mt-2 text-xs text-neutral-400">Sizes of one product share the same stock, so receiving the same stock under two sizes counts twice.</p>
          </Field>
        )}

        <Field label="Notes">
          <input value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder="e.g. receiving reference, source" className="w-full rounded border border-neutral-300 px-3 py-2 text-sm" />
        </Field>

        {error && <p className="mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>}

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={handleClose} className="rounded border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700">Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={saving || !productId || !locationId || filled.length === 0}
            className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {saving ? <BusyLabel>Receiving...</BusyLabel> : filled.length > 1 ? `Receive ${filled.length} sizes` : "Receive stock"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</label>
      {children}
    </div>
  );
}
