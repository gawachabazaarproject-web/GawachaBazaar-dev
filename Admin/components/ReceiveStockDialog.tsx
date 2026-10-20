"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { fetchAdminProducts, fetchAdminProductDetail, AdminProductListItem, ProductVariant } from "@/lib/products";
import { ReceiveStockForm } from "@/components/ReceiveStockForm";

/** Receive stock: pick a product, then add stock to any of its sizes in one form. */
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

  useEffect(() => {
    if (!open) return;
    const token = getAccessToken();
    if (!token) return;
    fetchAdminProducts(token, { page_size: 100 }).then((r) => setProducts(r.items)).catch(() => undefined);
    if (initialProductId) setProductId(String(initialProductId));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialProductId]);

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

  const handleClose = () => {
    setProductId("");
    setVariants([]);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded bg-white p-6 shadow-xl">
        <h2 className="mb-4 font-display text-lg font-semibold text-primary-900">Receive stock</h2>

        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">Product</label>
        <select
          value={productId}
          onChange={(e) => setProductId(e.target.value)}
          className="mb-3 w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">Choose a product</option>
          {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>

        {productId ? (
          <ReceiveStockForm variants={variants} onReceived={onReceived} onCancel={handleClose} />
        ) : (
          <div className="flex justify-end">
            <button onClick={handleClose} className="rounded border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700">Cancel</button>
          </div>
        )}
      </div>
    </div>
  );
}
