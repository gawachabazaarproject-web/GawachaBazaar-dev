"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  Category,
  CatalogApiError,
  createPrice,
  createProduct,
  createVariant,
  fetchCategories,
  updateProduct,
  uploadProductImage,
  VARIANT_UNITS,
} from "@/lib/products";
import { PageHeader } from "@/components/PageHeader";
import { Icon } from "@/components/icons";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

interface VariantRow {
  name: string;
  unit: string;
  quantity: string;
  price: string;
  sku: string;
}

const emptyVariant = (): VariantRow => ({ name: "", unit: "KG", quantity: "1", price: "", sku: "" });

const inputCls =
  "w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500";

export default function NewProductPage() {
  const { getAccessToken } = useAuth();
  const router = useRouter();

  const [categories, setCategories] = useState<Category[]>([]);
  const [name, setName] = useState("");
  const [categoryId, setCategoryId] = useState("");
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
    const usable = variants.filter((v) => v.name.trim() || v.price.trim());
    if (usable.length === 0 || usable.some((v) => !v.name.trim() || !v.price.trim())) {
      setError("Give every size/pack a name and a price.");
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
      });
      productId = product.id;
      setCreatedId(product.id);

      if (photo) {
        setProgress("Uploading photo...");
        await uploadProductImage(token, product.id, photo, { altText: name.trim(), isPrimary: true });
      }

      for (let i = 0; i < usable.length; i++) {
        const v = usable[i];
        setProgress(`Adding ${v.name.trim()}...`);
        const sku = (v.sku.trim() || `${effectiveSlug}-${slugify(v.name)}`).toUpperCase();
        const created = await createVariant(token, product.id, {
          name: v.name.trim(),
          sku,
          unit: v.unit,
          quantity: v.quantity || "1",
          status: "ACTIVE",
        });
        await createPrice(token, created.id, v.price.trim());
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
          <select required value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className={`${inputCls} bg-white`}>
            <option value="">Choose a category</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
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
          <div className="space-y-2">
            {variants.map((v, i) => (
              <div key={i} className="grid grid-cols-12 items-center gap-2">
                <input
                  value={v.name}
                  onChange={(e) => updateVariant(i, { name: e.target.value })}
                  placeholder="Name (e.g. 1 kg)"
                  className={`${inputCls} col-span-4`}
                />
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={v.quantity}
                  onChange={(e) => updateVariant(i, { quantity: e.target.value })}
                  aria-label="Quantity"
                  className={`${inputCls} col-span-2`}
                />
                <select
                  value={v.unit}
                  onChange={(e) => updateVariant(i, { unit: e.target.value })}
                  aria-label="Unit"
                  className={`${inputCls} col-span-2 bg-white`}
                >
                  {VARIANT_UNITS.map((u) => (
                    <option key={u} value={u}>{u}</option>
                  ))}
                </select>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={v.price}
                  onChange={(e) => updateVariant(i, { price: e.target.value })}
                  placeholder="₹ Price"
                  className={`${inputCls} col-span-3`}
                />
                <button
                  type="button"
                  disabled={variants.length === 1}
                  onClick={() => setVariants((rows) => rows.filter((_, idx) => idx !== i))}
                  aria-label="Remove size"
                  className="col-span-1 text-lg text-neutral-400 hover:text-status-danger disabled:opacity-30"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setVariants((rows) => [...rows, emptyVariant()])}
            className="mt-2 text-sm font-medium text-primary-700 hover:underline"
          >
            + Add another size
          </button>
          <p className="mt-1 text-xs text-neutral-400">SKUs are generated automatically. Add stock afterwards from Inventory.</p>
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
                <Field key={i} label={`SKU - ${v.name || `size ${i + 1}`}`}>
                  <input
                    value={v.sku}
                    onChange={(e) => updateVariant(i, { sku: e.target.value })}
                    placeholder={`${effectiveSlug}-${slugify(v.name)}`.toUpperCase()}
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
          {saving ? progress ?? "Saving..." : "Save product"}
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
