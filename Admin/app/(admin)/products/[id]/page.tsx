"use client";

import React, { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  AdminProductDetail,
  Category,
  CatalogApiError,
  createPrice,
  createVariant,
  deleteImage,
  deleteVariant,
  fetchAdminProductDetail,
  fetchCategories,
  fetchProductActivity,
  PRODUCT_STATUSES,
  ratePerBaseUnit,
  sizeLabel,
  ProductActivityEntry,
  updateImage,
  updateProduct,
  updateVariant,
  uploadProductImage,
  VARIANT_UNITS,
} from "@/lib/products";
import { formatDateTime, formatMoney } from "@/lib/format";
import { ErrorState } from "@/components/ErrorState";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ImageDropzone } from "@/components/ImageDropzone";
import { Icon } from "@/components/icons";
import { BusyLabel, PageLoader } from "@/components/Spinner";

export default function ProductDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const productId = Number(id);
  const { getAccessToken, user } = useAuth();
  const router = useRouter();

  const [product, setProduct] = useState<AdminProductDetail | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [activity, setActivity] = useState<ProductActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [general, setGeneral] = useState({ name: "", slug: "", category_id: "", description: "", status: "" });
  const [savingGeneral, setSavingGeneral] = useState(false);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);

  const canEdit = user && hasPermission(user.roles, "products.update");
  const canManageMedia = user && hasPermission(user.roles, "products.manage_media");
  const canManagePricing = user && hasPermission(user.roles, "products.manage_pricing");

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await fetchAdminProductDetail(token, productId);
      setProduct(detail);
      setGeneral({
        name: detail.name,
        slug: detail.slug,
        category_id: String(detail.category.id),
        description: detail.description ?? "",
        status: detail.status,
      });
      setIsDirty(false);
      fetchProductActivity(token, productId).then(setActivity).catch(() => undefined);
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to load this product.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  useEffect(() => {
    load();
    fetchCategories().then(setCategories).catch(() => undefined);
  }, [load]);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  const handleBack = () => {
    if (isDirty && !window.confirm("You have unsaved changes. Leave without saving?")) return;
    router.push("/products");
  };

  const updateGeneralField = (field: keyof typeof general, value: string) => {
    setGeneral((g) => ({ ...g, [field]: value }));
    setIsDirty(true);
  };

  const handleSaveGeneral = async () => {
    const token = getAccessToken();
    if (!token) return;
    setSavingGeneral(true);
    setGeneralError(null);
    try {
      await updateProduct(token, productId, {
        name: general.name,
        slug: general.slug,
        category_id: Number(general.category_id),
        description: general.description || null,
        status: general.status,
      });
      await load();
    } catch (err) {
      setGeneralError(err instanceof CatalogApiError ? err.message : "Unable to save changes.");
    } finally {
      setSavingGeneral(false);
    }
  };

  if (loading) return <PageLoader label="Loading product..." />;
  if (error || !product) return <ErrorState message={error ?? "Product not found."} onRetry={load} />;

  const sizeOf = (variantId: number) => {
    const v = product.variants.find((x) => x.id === variantId);
    return v ? sizeLabel(v.quantity, v.unit) : "";
  };
  const primaryImage = product.images.find((i) => i.is_primary) ?? product.images[0];
  const firstVariant = product.variants[0];

  return (
    <div className="mx-auto max-w-4xl">
      <button onClick={handleBack} className="mb-4 flex items-center gap-1 text-sm text-neutral-500 hover:text-primary-800">
        <Icon name="chevron-left" size={14} /> Back to products
      </button>

      <div className="mb-6 flex items-start gap-4">
        <div className="h-20 w-20 shrink-0 overflow-hidden rounded bg-neutral-100">
          {primaryImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={primaryImage.image_url} alt="" className="h-full w-full object-cover" />
          ) : null}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="font-display text-2xl font-semibold text-primary-900">{product.name}</h1>
            <StatusBadge status={product.status} />
          </div>
          <p className="mt-1 text-sm text-neutral-500">
            {product.category.name}
            {firstVariant?.current_price &&
              ` · ${formatMoney(firstVariant.current_price.price, firstVariant.current_price.currency)}`}
          </p>
        </div>
      </div>

      <Section title="General">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Name">
            <input
              value={general.name}
              onChange={(e) => updateGeneralField("name", e.target.value)}
              disabled={!canEdit}
              className="w-full rounded border border-neutral-300 px-3 py-2 text-sm disabled:bg-neutral-50"
            />
          </Field>
          <Field label="Slug">
            <input
              value={general.slug}
              onChange={(e) => updateGeneralField("slug", e.target.value)}
              disabled={!canEdit}
              className="w-full rounded border border-neutral-300 px-3 py-2 text-sm font-mono disabled:bg-neutral-50"
            />
          </Field>
          <Field label="Category">
            <select
              value={general.category_id}
              onChange={(e) => updateGeneralField("category_id", e.target.value)}
              disabled={!canEdit}
              className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm disabled:bg-neutral-50"
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Status" hint={general.status === "ARCHIVED" ? "Archived products are hidden from customers." : undefined}>
            <select
              value={general.status}
              onChange={(e) => updateGeneralField("status", e.target.value)}
              disabled={!canEdit}
              className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm disabled:bg-neutral-50"
            >
              {PRODUCT_STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </Field>
          <div className="col-span-2">
            <Field label="Description">
              <textarea
                value={general.description}
                onChange={(e) => updateGeneralField("description", e.target.value)}
                disabled={!canEdit}
                rows={3}
                className="w-full rounded border border-neutral-300 px-3 py-2 text-sm disabled:bg-neutral-50"
              />
            </Field>
          </div>
        </div>
        {generalError && (
          <p className="mb-2 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">
            {generalError}
          </p>
        )}
        {canEdit && (
          <button
            onClick={handleSaveGeneral}
            disabled={!isDirty || savingGeneral}
            className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {savingGeneral ? <BusyLabel>Saving...</BusyLabel> : "Save changes"}
          </button>
        )}
      </Section>

      <MediaSection product={product} canManageMedia={!!canManageMedia} onChange={load} />

      <VariantsSection product={product} canManagePricing={!!canManagePricing} canEdit={!!canEdit} onChange={load} />

      <Section title="Inventory">
        <p className="mb-2 text-sm text-neutral-500">
          Stock is managed in the Inventory module - shown here read-only.
        </p>
        <div className="divide-y divide-neutral-100">
          {product.variant_stock.map((vs) => (
            <div key={vs.variant_id} className="flex items-center justify-between py-2 text-sm">
              <span className="text-neutral-700">{sizeOf(vs.variant_id)}</span>
              <span className={Number(vs.available_quantity) === 0 ? "font-semibold text-status-danger" : "text-neutral-800"}>
                {vs.available_quantity} units
              </span>
            </div>
          ))}
        </div>
        <a href="/inventory" className="mt-3 inline-block text-sm font-semibold text-primary-700 hover:underline">
          View inventory →
        </a>
      </Section>

      <Section title="Merchandising">
        <p className="text-sm text-neutral-400">
          Featured/seasonal/homepage-visibility flags don&apos;t exist on the Product model yet - there is nothing
          real to control here until that backend work is done.
        </p>
      </Section>

      <Section title="Reviews">
        <p className="text-sm text-neutral-400">
          No review domain exists in the backend yet - there is nothing to summarize until that module is built.
        </p>
      </Section>

      <Section title="Activity">
        {activity.length === 0 ? (
          <p className="text-sm text-neutral-400">No recorded activity yet.</p>
        ) : (
          <div className="space-y-2">
            {activity.map((entry) => (
              <div key={`${entry.resource_type}-${entry.id}`} className="flex items-start justify-between text-sm">
                <div>
                  <p className="text-neutral-800">
                    {formatActivityAction(entry)} <span className="text-neutral-400">by {entry.admin_name}</span>
                  </p>
                </div>
                <p className="shrink-0 text-xs text-neutral-400">{formatDateTime(entry.created_at)}</p>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

function formatActivityAction(entry: ProductActivityEntry): string {
  if (entry.previous_state && entry.new_state) {
    return `${entry.action} — ${entry.previous_state} → ${entry.new_state}`;
  }
  if (entry.new_state) return `${entry.action} — ${entry.new_state}`;
  return entry.action;
}

function MediaSection({
  product,
  canManageMedia,
  onChange,
}: {
  product: AdminProductDetail;
  canManageMedia: boolean;
  onChange: () => void;
}) {
  const { getAccessToken } = useAuth();
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (file: File) => {
    const token = getAccessToken();
    if (!token) return;
    setError(null);
    try {
      await uploadProductImage(token, product.id, file, { isPrimary: product.images.length === 0 });
      onChange();
    } catch (err) {
      throw new Error(err instanceof CatalogApiError ? err.message : "Unable to upload this image.");
    }
  };

  const handleSetPrimary = async (imageId: number) => {
    const token = getAccessToken();
    if (!token) return;
    await updateImage(token, imageId, { is_primary: true }).catch(() => undefined);
    onChange();
  };

  const handleDelete = async (imageId: number) => {
    const token = getAccessToken();
    if (!token) return;
    await deleteImage(token, imageId).catch(() => undefined);
    onChange();
  };

  return (
    <Section title="Media">
      {product.images.length === 0 ? (
        <p className="mb-3 text-sm text-neutral-400">No images yet.</p>
      ) : (
        <div className="mb-4 flex flex-wrap gap-3">
          {product.images.map((img) => (
            <div key={img.id} className="w-28">
              <div className="relative h-28 w-28 overflow-hidden rounded border border-neutral-200 bg-neutral-100">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={img.image_url} alt={img.alt_text ?? ""} className="h-full w-full object-cover" />
                {img.is_primary && (
                  <span className="absolute left-1 top-1 rounded bg-primary-800 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                    Primary
                  </span>
                )}
              </div>
              {canManageMedia && (
                <div className="mt-1 flex justify-between text-xs">
                  {!img.is_primary && (
                    <button onClick={() => handleSetPrimary(img.id)} className="text-primary-700 hover:underline">
                      Set primary
                    </button>
                  )}
                  <button onClick={() => handleDelete(img.id)} className="ml-auto text-status-danger hover:underline">
                    Remove
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {canManageMedia && (
        <ImageDropzone label="Add an image" onUpload={handleUpload} />
      )}
      {error && <p className="mt-2 text-sm text-status-danger">{error}</p>}
    </Section>
  );
}

function VariantsSection({
  product,
  canManagePricing,
  canEdit,
  onChange,
}: {
  product: AdminProductDetail;
  canManagePricing: boolean;
  canEdit: boolean;
  onChange: () => void;
}) {
  const { getAccessToken } = useAuth();
  const [showAddVariant, setShowAddVariant] = useState(false);
  const [newVariant, setNewVariant] = useState({ unit: "KG", quantity: "", price: "" });
  const [addingVariant, setAddingVariant] = useState(false);
  const [priceDialogVariant, setPriceDialogVariant] = useState<number | null>(null);
  const [newPrice, setNewPrice] = useState("");
  const [savingPrice, setSavingPrice] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingVariant, setEditingVariant] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ unit: "KG", quantity: "" });
  const [savingEdit, setSavingEdit] = useState(false);
  const [deleteVariantId, setDeleteVariantId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleAddVariant = async () => {
    const token = getAccessToken();
    if (!token) return;
    setAddingVariant(true);
    setError(null);
    try {
      const label = sizeLabel(newVariant.quantity, newVariant.unit);
      const sku = `${product.slug}-${label.replace(/[^a-z0-9]+/gi, "-")}`.toUpperCase();
      const created = await createVariant(token, product.id, {
        name: label,
        sku,
        unit: newVariant.unit,
        quantity: newVariant.quantity,
        status: "ACTIVE",
      });
      if (Number(newVariant.price) > 0) await createPrice(token, created.id, newVariant.price);
      setShowAddVariant(false);
      setNewVariant({ unit: "KG", quantity: "", price: "" });
      onChange();
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to add this variant.");
    } finally {
      setAddingVariant(false);
    }
  };

  const handleToggleVariantStatus = async (variantId: number, currentStatus: string) => {
    const token = getAccessToken();
    if (!token) return;
    const next = currentStatus === "ACTIVE" ? "INACTIVE" : "ACTIVE";
    await updateVariant(token, variantId, { status: next }).catch(() => undefined);
    onChange();
  };

  const startEdit = (v: AdminProductDetail["variants"][number]) => {
    setEditingVariant(v.id);
    setEditForm({ unit: v.unit, quantity: String(Number(v.quantity)) });
    setError(null);
  };

  const handleSaveEdit = async () => {
    const token = getAccessToken();
    if (!token || editingVariant === null) return;
    setSavingEdit(true);
    setError(null);
    try {
      await updateVariant(token, editingVariant, {
        name: sizeLabel(editForm.quantity, editForm.unit),
        unit: editForm.unit,
        quantity: editForm.quantity,
      });
      setEditingVariant(null);
      onChange();
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to update this variant.");
    } finally {
      setSavingEdit(false);
    }
  };

  const handleConfirmDelete = async () => {
    const token = getAccessToken();
    if (!token || deleteVariantId === null) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteVariant(token, deleteVariantId);
      setDeleteVariantId(null);
      onChange();
    } catch (err) {
      setDeleteVariantId(null);
      setError(err instanceof CatalogApiError ? err.message : "Unable to delete this variant.");
    } finally {
      setDeleting(false);
    }
  };

  const activeVariant = product.variants.find((v) => v.id === priceDialogVariant);
  const variantToDelete = product.variants.find((v) => v.id === deleteVariantId);

  const handleConfirmPrice = async () => {
    const token = getAccessToken();
    if (!token || !priceDialogVariant) return;
    setSavingPrice(true);
    setError(null);
    try {
      await createPrice(token, priceDialogVariant, newPrice);
      setPriceDialogVariant(null);
      setNewPrice("");
      onChange();
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to update this price.");
    } finally {
      setSavingPrice(false);
    }
  };

  return (
    <Section title={`Variants & Pricing (${product.variants.length})`}>
      <div className="divide-y divide-neutral-100">
        {product.variants.map((v) => (
          <div key={v.id} className="flex items-center justify-between py-2 text-sm">
            <div>
              <p className="font-medium text-neutral-800">{sizeLabel(v.quantity, v.unit)}</p>
              <p className="text-xs text-neutral-500">
                {product.name}
                {v.current_price && ratePerBaseUnit(v.current_price.price, v.quantity, v.unit)
                  ? ` · ${ratePerBaseUnit(v.current_price.price, v.quantity, v.unit)}`
                  : ""}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="font-medium text-neutral-800">
                {v.current_price ? formatMoney(v.current_price.price, v.current_price.currency) : "No price set"}
              </span>
              <StatusBadge status={v.status} />
              {canManagePricing && (
                <button
                  onClick={() => { setPriceDialogVariant(v.id); setNewPrice(v.current_price?.price ?? ""); }}
                  className="text-xs font-semibold text-primary-700 hover:underline"
                >
                  Change price
                </button>
              )}
              {canEdit && (
                <button
                  onClick={() => handleToggleVariantStatus(v.id, v.status)}
                  className="text-xs font-semibold text-neutral-500 hover:underline"
                >
                  {v.status === "ACTIVE" ? "Deactivate" : "Activate"}
                </button>
              )}
              {canEdit && (
                <button onClick={() => startEdit(v)} className="text-xs font-semibold text-primary-700 hover:underline">
                  Edit
                </button>
              )}
              {canEdit && (
                <button
                  onClick={() => setDeleteVariantId(v.id)}
                  className="text-xs font-semibold text-status-danger hover:underline"
                >
                  Delete
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {error && <p className="mt-2 text-sm text-status-danger">{error}</p>}

      {canEdit && (
        <div className="mt-3">
          {!showAddVariant ? (
            <button onClick={() => setShowAddVariant(true)} className="text-sm font-semibold text-primary-700 hover:underline">
              + Add variant
            </button>
          ) : (
            <div className="mt-2 grid grid-cols-3 gap-2 rounded border border-neutral-200 p-3">
              <input
                type="number"
                min="0"
                step="any"
                placeholder="Amount (e.g. 250)"
                value={newVariant.quantity}
                onChange={(e) => setNewVariant((v) => ({ ...v, quantity: e.target.value }))}
                className="rounded border border-neutral-300 px-2 py-1.5 text-sm"
              />
              <select
                value={newVariant.unit}
                onChange={(e) => setNewVariant((v) => ({ ...v, unit: e.target.value }))}
                className="rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm"
              >
                {VARIANT_UNITS.map((u) => (
                  <option key={u} value={u}>{u}</option>
                ))}
              </select>
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="₹ Price"
                value={newVariant.price}
                onChange={(e) => setNewVariant((v) => ({ ...v, price: e.target.value }))}
                className="rounded border border-neutral-300 px-2 py-1.5 text-sm"
              />
              <div className="col-span-3 flex gap-2">
                <button
                  onClick={handleAddVariant}
                  disabled={addingVariant || !(Number(newVariant.quantity) > 0)}
                  className="rounded bg-primary-800 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40"
                >
                  {addingVariant ? <BusyLabel>Adding...</BusyLabel> : "Add"}
                </button>
                <button onClick={() => setShowAddVariant(false)} className="rounded border border-neutral-300 px-3 py-1.5 text-sm">
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <ConfirmDialog
        open={editingVariant !== null}
        title="Edit size"
        description="Change the amount or unit of this size. Its price and stock stay as they are."
        confirmLabel="Save"
        loading={savingEdit}
        onCancel={() => setEditingVariant(null)}
        onConfirm={handleSaveEdit}
      >
        <div className="mt-2 flex gap-2">
          <input
            type="number"
            min="0"
            step="any"
            value={editForm.quantity}
            onChange={(e) => setEditForm((f) => ({ ...f, quantity: e.target.value }))}
            placeholder="Amount (e.g. 250)"
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
          />
          <select
            value={editForm.unit}
            onChange={(e) => setEditForm((f) => ({ ...f, unit: e.target.value }))}
            className="rounded border border-neutral-300 bg-white px-3 py-2 text-sm"
          >
            {VARIANT_UNITS.map((u) => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
        </div>
      </ConfirmDialog>

      <ConfirmDialog
        open={deleteVariantId !== null}
        title="Delete variant?"
        description={`Permanently delete the ${variantToDelete ? sizeLabel(variantToDelete.quantity, variantToDelete.unit) : "selected"} size and its price. Variants with order, quote or stock history can't be deleted - deactivate those instead.`}
        confirmLabel="Delete variant"
        loading={deleting}
        onCancel={() => setDeleteVariantId(null)}
        onConfirm={handleConfirmDelete}
      />

      <ConfirmDialog
        open={priceDialogVariant !== null}
        title="Change price?"
        description={
          activeVariant?.current_price
            ? `Current price: ${formatMoney(activeVariant.current_price.price, activeVariant.current_price.currency)}. This creates a new price effective immediately - the old price is kept as history, not overwritten.`
            : "This variant has no price yet. This creates its first price, effective immediately."
        }
        confirmLabel="Update price"
        loading={savingPrice}
        onCancel={() => setPriceDialogVariant(null)}
        onConfirm={handleConfirmPrice}
      >
        <input
          type="number"
          value={newPrice}
          onChange={(e) => setNewPrice(e.target.value)}
          placeholder="New price (₹)"
          className="mt-2 w-full rounded border border-neutral-300 px-3 py-2 text-sm"
        />
      </ConfirmDialog>
    </Section>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4 rounded border border-neutral-200 bg-white p-4">
      <h2 className="mb-3 font-display text-base font-semibold text-primary-900">{title}</h2>
      {children}
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</label>
      {children}
      {hint && <p className="mt-1 text-xs text-neutral-400">{hint}</p>}
    </div>
  );
}
