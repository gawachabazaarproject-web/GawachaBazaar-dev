"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  Category,
  CatalogApiError,
  createPrice,
  createProduct,
  createVariant,
  fetchCategories,
  ratePerBaseUnit,
  sizeLabel,
  updateProduct,
  uploadProductImage,
  VARIANT_UNITS,
} from "@/lib/products";
import { CategoryChecklist } from "@/components/CategoryChecklist";
import { PageHeader } from "@/components/PageHeader";
import { Icon } from "@/components/icons";
import { BusyLabel } from "@/components/Spinner";
import { SearchableSelect, categoryOptions } from "@/components/SearchableSelect";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

interface VariantRow {
  unit: string;
  quantity: string;
  /** Price of one whole pack (e.g. Rs 20 for a 250 g pack). */
  price: string;
  sku: string;
}

/** Price of one whole pack in rupees ("" when it is not a usable amount). */
function packPrice(v: VariantRow): string {
  const price = Number(v.price);
  return Number(v.quantity) > 0 && price > 0 ? price.toFixed(2) : "";
}

const emptyVariant = (): VariantRow => ({ unit: "KG", quantity: "", price: "", sku: "" });

const inputCls =
  "w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500";

export default function NewProductPage() {
  const { getAccessToken } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [categories, setCategories] = useState<Category[]>([]);
  const [name, setName] = useState("");
  // Pre-selected when arriving from a category page ("+ Add product").
  const [categoryId, setCategoryId] = useState(searchParams.get("category") ?? "");
  const [extraCategoryIds, setExtraCategoryIds] = useState<number[]>([]);
  const [description, setDescription] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [variants, setVariants] = useState<VariantRow[]>([emptyVariant()]);
  const [publish, setPublish] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);

  const [saving, setSaving] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createdId, setCreatedId] = useState<number | null>(null);

  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => undefined);
  }, []);

  const photoPreview = useMemo(() => (photo ? URL.createObjectURL(photo) : null), [photo]);
  useEffect(() => () => { if (photoPreview) URL.revokeObjectURL(photoPreview); }, [photoPreview]);

  const effectiveSlug = slugTouched ? slug : slugify(name);

  const updateVariant = (i: number, patch: Partial<VariantRow>) =>
    setVariants((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = getAccessToken();
    if (!token) return;
    if (!categoryId) {
      setError("Choose a category.");
      return;
    }
    const usable = variants.filter((v) => v.quantity.trim() || v.price.trim());
    if (usable.length === 0 || usable.some((v) => !(Number(v.quantity) > 0) || !packPrice(v))) {
      setError("Give every pack a size and a price, both greater than 0.");
      return;
    }

    setSaving(true);
    setError(null);
    let productId: number | null = null;
    try {
      setProgress("Creating product...");
      const product = await createProduct(token, {
        category_id: Number(categoryId),
        name: name.trim(),
        slug: effectiveSlug,
        description: description.trim() || null,
        status: "DRAFT",
        extra_category_ids: extraCategoryIds.filter((id) => String(id) !== categoryId),
      });
      productId = product.id;
      setCreatedId(product.id);

      if (photo) {
        setProgress("Uploading photo...");
        await uploadProductImage(token, product.id, photo, { altText: name.trim(), isPrimary: true });
      }

      for (let i = 0; i < usable.length; i++) {
        const v = usable[i];
        const label = sizeLabel(v.quantity, v.unit);
        setProgress(`Adding ${label}...`);
        const sku = (v.sku.trim() || `${effectiveSlug}-${slugify(label)}`).toUpperCase();
        const created = await createVariant(token, product.id, {
          name: label,
          sku,
          unit: v.unit,
          quantity: v.quantity,
          status: "ACTIVE",
        });
        await createPrice(token, created.id, packPrice(v));
      }

      if (publish) {
        setProgress("Publishing...");
        await updateProduct(token, product.id, { status: "ACTIVE" });
      }
      router.push(`/products/${product.id}`);
    } catch (err) {
      const msg = err instanceof CatalogApiError ? err.message : "Something went wrong.";
      setError(
        productId
          ? `${msg} The product was created as a draft - finish it from its page.`
          : msg,
      );
    } finally {
      setSaving(false);
      setProgress(null);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <button onClick={() => router.push("/products")} className="mb-4 flex items-center gap-1 text-sm text-neutral-500 hover:text-primary-800">
        <Icon name="chevron-left" size={14} /> Back to products
      </button>

      <PageHeader eyebrow="Catalog" title="Add product" description="Everything in one step - fill this in and save." />

      <form onSubmit={handleSubmit} className="space-y-5 rounded border border-neutral-200 bg-white p-6">
        <Field label="Product name" required>
          <input required autoFocus value={name} onChange={(e) => setName(e.target.value)} className={inputCls} placeholder="e.g. Fresh Tomatoes" />
        </Field>

        <Field label="Category" required>
          <SearchableSelect
            required
            value={categoryId}
            onChange={setCategoryId}
            placeholder="Choose a category"
            options={categoryOptions(categories)}
          />
        </Field>

        <Field label="Also show in" hint="Optional - the product will appear in these categories and subcategories too.">
          <CategoryChecklist
            categories={categories}
            mainCategoryId={categoryId}
            selected={extraCategoryIds}
            onChange={setExtraCategoryIds}
          />
        </Field>

        <Field label="Photo">
          <div className="flex items-center gap-4">
            {photoPreview && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={photoPreview} alt="Preview" className="h-20 w-20 rounded border border-neutral-200 object-cover" />
            )}
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
              className="text-sm text-neutral-600"
            />
          </div>
        </Field>

        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">
            Sizes &amp; prices <span className="text-status-danger">*</span>
          </label>
          <div className="space-y-3">
            {variants.map((v, i) => {
              const rate = packPrice(v) ? ratePerBaseUnit(v.price, v.quantity, v.unit) : null;
              return (
                <div key={i} className="rounded border border-neutral-200 p-3">
                  <div className="grid grid-cols-12 items-end gap-2">
                    <div className="col-span-5">
                      <span className="mb-1 block text-xs text-neutral-500">Pack size</span>
                      <div className="flex gap-2">
                        <input
                          type="number"
                          min="0"
                          step="any"
                          value={v.quantity}
                          onChange={(e) => updateVariant(i, { quantity: e.target.value })}
                          placeholder="1"
                          aria-label="Pack size"
                          className={`${inputCls} w-20`}
                        />
                        <select
                          value={v.unit}
                          onChange={(e) => updateVariant(i, { unit: e.target.value })}
                          aria-label="Unit"
                          className={`${inputCls} bg-white`}
                        >
                          {VARIANT_UNITS.map((u) => (
                            <option key={u} value={u}>{u}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="col-span-6">
                      <span className="mb-1 block text-xs text-neutral-500">Price of this pack</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-neutral-500">₹</span>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={v.price}
                          onChange={(e) => updateVariant(i, { price: e.target.value })}
                          placeholder="20"
                          aria-label="Price of this pack"
                          className={inputCls}
                        />
                      </div>
                    </div>
                    <button
                      type="button"
                      disabled={variants.length === 1}
                      onClick={() => setVariants((rows) => rows.filter((_, idx) => idx !== i))}
                      aria-label="Remove size"
                      className="col-span-1 pb-2 text-lg text-neutral-400 hover:text-status-danger disabled:opacity-30"
                    >
                      ×
                    </button>
                  </div>
                  {packPrice(v) && (
                    <p className="mt-2 text-sm font-medium text-primary-900">
                      Pack of {sizeLabel(v.quantity, v.unit)} sells for ₹{packPrice(v)}
                      {rate && <span className="font-normal text-neutral-500"> · works out to {rate}</span>}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
          <button
            type="button"
            onClick={() => setVariants((rows) => [...rows, emptyVariant()])}
            className="mt-2 text-sm font-medium text-primary-700 hover:underline"
          >
            + Add another pack size
          </button>
          <p className="mt-1 text-xs text-neutral-400">Enter how big one pack is and what that pack costs - e.g. 250 G for ₹20 (the per-kg rate is shown for you). Names and SKUs are made for you. Add stock afterwards from Inventory.</p>
        </div>

        <Field label="Description">
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className={inputCls} />
        </Field>

        <label className="flex items-center gap-2 text-sm text-neutral-700">
          <input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} />
          Make visible to customers right away
        </label>

        <div>
          <button type="button" onClick={() => setShowAdvanced((s) => !s)} className="text-xs text-neutral-500 hover:text-primary-800">
            {showAdvanced ? "Hide" : "Show"} advanced (URL slug, SKUs)
          </button>
          {showAdvanced && (
            <div className="mt-3 space-y-3 rounded border border-neutral-200 p-3">
              <Field label="URL slug" hint="Generated from the name; change only if needed.">
                <input
                  value={effectiveSlug}
                  onChange={(e) => { setSlugTouched(true); setSlug(e.target.value); }}
                  className={`${inputCls} font-mono`}
                />
              </Field>
              {variants.map((v, i) => (
                <Field key={i} label={`SKU - ${v.quantity ? sizeLabel(v.quantity, v.unit) : `size ${i + 1}`}`}>
                  <input
                    value={v.sku}
                    onChange={(e) => updateVariant(i, { sku: e.target.value })}
                    placeholder={`${effectiveSlug}-${slugify(v.quantity ? sizeLabel(v.quantity, v.unit) : "")}`.toUpperCase()}
                    className={`${inputCls} font-mono`}
                  />
                </Field>
              ))}
            </div>
          )}
        </div>

        {error && (
          <p className="rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">
            {error}{" "}
            {createdId && (
              <button type="button" onClick={() => router.push(`/products/${createdId}`)} className="font-semibold underline">
                Open product
              </button>
            )}
          </p>
        )}

        <button
          type="submit"
          disabled={saving}
          className="w-full rounded bg-primary-800 py-2.5 text-sm font-semibold text-white hover:bg-primary-700 disabled:opacity-60"
        >
          {saving ? <BusyLabel>{progress ?? "Saving..."}</BusyLabel> : "Save product"}
        </button>
      </form>
    </div>
  );
}

function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">
        {label} {required && <span className="text-status-danger">*</span>}
      </label>
      {children}
      {hint && <p className="mt-1 text-xs text-neutral-400">{hint}</p>}
    </div>
  );
}
