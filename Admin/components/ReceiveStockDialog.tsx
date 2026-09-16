"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { fetchLocations, InventoryApiError, Location, receiveStock } from "@/lib/inventory";
import { fetchAdminProducts, fetchAdminProductDetail, AdminProductListItem, ProductVariant } from "@/lib/products";

export function ReceiveStockDialog({ open, onClose, onReceived }: { open: boolean; onClose: () => void; onReceived: () => void }) {
  const { getAccessToken } = useAuth();

  const [products, setProducts] = useState<AdminProductListItem[]>([]);
  const [productId, setProductId] = useState("");
  const [variants, setVariants] = useState<ProductVariant[]>([]);
  const [variantId, setVariantId] = useState("");
  const [locations, setLocations] = useState<Location[]>([]);
  const [locationId, setLocationId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [remarks, setRemarks] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const token = getAccessToken();
    if (!token) return;
    fetchAdminProducts(token, { page_size: 100 }).then((r) => setProducts(r.items)).catch(() => undefined);
    fetchLocations(token).then(setLocations).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
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

  const reset = () => {
    setProductId("");
    setVariantId("");
    setLocationId("");
    setQuantity("");
    setRemarks("");
    setError(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async () => {
    const token = getAccessToken();
    if (!token || !productId || !variantId || !locationId || !quantity) return;
    setSaving(true);
    setError(null);
    try {
      await receiveStock(token, {
        variant_id: Number(variantId),
        location_id: Number(locationId),
        quantity,
        remarks: remarks || undefined,
      });
      handleClose();
      onReceived();
    } catch (err) {
      setError(err instanceof InventoryApiError ? err.message : "Unable to receive stock.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded bg-white p-6 shadow-xl">
        <h2 className="mb-4 font-display text-lg font-semibold text-primary-900">Receive stock</h2>

        <Field label="Product">
          <select value={productId} onChange={(e) => { setProductId(e.target.value); setVariantId(""); }} className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm">
            <option value="">Choose a product</option>
            {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </Field>

        {productId && (
          <Field label="Variant / SKU">
            <select value={variantId} onChange={(e) => setVariantId(e.target.value)} className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm">
              <option value="">Choose a variant</option>
              {variants.map((v) => <option key={v.id} value={v.id}>{v.name} ({v.sku})</option>)}
            </select>
          </Field>
        )}

        <Field label="Warehouse">
          <select value={locationId} onChange={(e) => setLocationId(e.target.value)} className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm">
            <option value="">Choose a warehouse</option>
            {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </Field>

        <Field label="Quantity">
          <input type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} className="w-full rounded border border-neutral-300 px-3 py-2 text-sm" />
        </Field>

        <Field label="Notes">
          <input value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder="e.g. receiving reference, source" className="w-full rounded border border-neutral-300 px-3 py-2 text-sm" />
        </Field>

        {error && <p className="mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>}

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={handleClose} className="rounded border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700">Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={saving || !productId || !variantId || !locationId || !quantity}
            className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {saving ? "Receiving..." : "Receive stock"}
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
