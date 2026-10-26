"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { fetchProductStock, ProductStockItem } from "@/lib/inventory";
import { fetchAdminProductDetail } from "@/lib/products";
import { AddStockDialog } from "@/components/StockDialogs";
import { SearchableSelect } from "@/components/SearchableSelect";

/**
 * "Receive stock" when no product is chosen yet: pick the product, then the
 * same short Add stock dialog every card uses. Works for warehouse staff too
 * (it reads the inventory list, not the product catalogue).
 */
export function ReceiveStockDialog({
  open,
  onClose,
  onDone,
  initialProductId,
}: {
  open: boolean;
  onClose: () => void;
  onDone: (message: string) => void;
  /** Skip the product choice when it is already known. */
  initialProductId?: number;
}) {
  const { getAccessToken } = useAuth();
  const [products, setProducts] = useState<ProductStockItem[]>([]);
  const [productId, setProductId] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!open) return;
    const token = getAccessToken();
    if (!token) return;
    setFailed(false);
    const fromList = () =>
      fetchProductStock(token, { page_size: 100 })
        .then((r) => {
          setProducts(r.items);
          if (initialProductId) setProductId(String(initialProductId));
        })
        .catch(() => setFailed(true));
    if (!initialProductId) {
      fromList();
      return;
    }
    // A known product: read its card directly (works past the first 100 products).
    fetchAdminProductDetail(token, initialProductId)
      .then((detail) => {
        if (!detail.stock) return fromList();
        setProducts([detail.stock]);
        setProductId(String(initialProductId));
      })
      .catch(() => fromList());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialProductId]);

  useEffect(() => {
    if (!open) setProductId("");
  }, [open]);

  useEffect(() => {
    if (!open || productId) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, productId, onClose]);

  if (!open) return null;

  const chosen = products.find((p) => String(p.product_id) === productId);
  if (chosen) {
    return (
      <AddStockDialog
        product={chosen}
        onClose={onClose}
        onDone={onDone}
      />
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:px-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Receive stock"
        className="w-full rounded-t-lg bg-white p-5 shadow-xl sm:max-w-md sm:rounded"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-3 font-display text-lg font-semibold text-primary-900">Receive stock</h2>
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">Which product?</label>
        <SearchableSelect
          value={productId}
          onChange={setProductId}
          placeholder="Choose a product"
          options={products.map((p) => ({ value: String(p.product_id), label: p.product_name }))}
        />
        {failed && <p role="alert" className="mt-3 text-sm text-status-danger">Couldn&apos;t load the products. Check your connection and try again.</p>}
        <div className="mt-4 flex justify-end">
          <button type="button" onClick={onClose} className="rounded border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
