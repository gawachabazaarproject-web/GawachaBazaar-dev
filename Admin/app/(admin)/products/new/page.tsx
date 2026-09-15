"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Category, CatalogApiError, createProduct, fetchCategories, PRODUCT_STATUSES } from "@/lib/products";
import { PageHeader } from "@/components/PageHeader";
import { Icon } from "@/components/icons";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

export default function NewProductPage() {
  const { getAccessToken } = useAuth();
  const router = useRouter();

  const [categories, setCategories] = useState<Category[]>([]);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [categoryId, setCategoryId] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("DRAFT");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => undefined);
  }, []);

  const handleNameChange = (value: string) => {
    setName(value);
    if (!slugTouched) setSlug(slugify(value));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = getAccessToken();
    if (!token) return;
    if (!categoryId) {
      setError("Choose a category.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const product = await createProduct(token, {
        category_id: Number(categoryId),
        name,
        slug,
        description: description || null,
        status,
      });
      router.push(`/products/${product.id}`);
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to create this product.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <button onClick={() => router.push("/products")} className="mb-4 flex items-center gap-1 text-sm text-neutral-500 hover:text-primary-800">
        <Icon name="chevron-left" size={14} /> Back to products
      </button>

      <PageHeader
        eyebrow="Catalog"
        title="Create product"
        description="General information first - add media, variants, and pricing after creating it."
      />

      <form onSubmit={handleSubmit} className="rounded border border-neutral-200 bg-white p-6">
        <h2 className="mb-4 font-display text-base font-semibold text-primary-900">General</h2>

        <Field label="Name" required>
          <input
            required
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
        </Field>

        <Field label="Slug" required hint="Used in the product's URL - lowercase, hyphenated.">
          <input
            required
            value={slug}
            onChange={(e) => { setSlugTouched(true); setSlug(e.target.value); }}
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm font-mono focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
        </Field>

        <Field label="Category" required>
          <select
            required
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">Choose a category</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </Field>

        <Field label="Description">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
        </Field>

        <Field label="Status" hint="DRAFT products are never shown to customers.">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm"
          >
            {PRODUCT_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </Field>

        {error && (
          <p className="mb-4 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={saving}
          className="w-full rounded bg-primary-800 py-2.5 text-sm font-semibold text-white hover:bg-primary-700 disabled:opacity-60"
        >
          {saving ? "Creating..." : "Create product"}
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
    <div className="mb-4">
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">
        {label} {required && <span className="text-status-danger">*</span>}
      </label>
      {children}
      {hint && <p className="mt-1 text-xs text-neutral-400">{hint}</p>}
    </div>
  );
}
