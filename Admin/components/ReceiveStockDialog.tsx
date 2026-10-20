"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { fetchAdminProducts, fetchAdminProductDetail, AdminProductListItem, ProductVariant } from "@/lib/products";
import { ReceiveStockForm } from "@/components/ReceiveStockForm";
import { SearchableSelect } from "@/components/SearchableSelect";

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
      <div className="max-h-[88vh] w-full max-w-lg overflow-y-auto rounded bg-white p-5 text-[13px] shadow-xl">
        <h2 className="mb-3 font-display text-base font-semibold text-primary-900">Receive stock</h2>

        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">Product</label>
        <SearchableSelect
          className="mb-3"
          value={productId}
          onChange={setProductId}
          placeholder="Choose a product"
          options={products.map((p) => ({ value: String(p.id), label: p.name }))}
        />

        <ReceiveStockForm
          productId={Number(productId) || 0}
          variants={variants}
          onReceived={onReceived}
          onCancel={handleClose}
          emptyHint={productId ? "This product has no sizes yet. Add a size first." : "Choose a product above to enter what arrived for each of its sizes."}
        />
      </div>
    </div>
  );
}
