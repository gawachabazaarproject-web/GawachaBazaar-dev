"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { CATEGORY_STATUSES, CategoryApiError, CategoryRef, createCategory, fetchAdminCategories } from "@/lib/categories";
import { PageHeader } from "@/components/PageHeader";
import { Icon } from "@/components/icons";

function slugify(value: string): string {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

export default function NewCategoryPage() {
  const { getAccessToken } = useAuth();
  const router = useRouter();

  const [categories, setCategories] = useState<CategoryRef[]>([]);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [parentId, setParentId] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("ACTIVE");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    fetchAdminCategories(token, { page: 1, page_size: 100 })
      .then((r) => setCategories(r.items))
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleNameChange = (value: string) => {
    setName(value);
    if (!slugTouched) setSlug(slugify(value));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = getAccessToken();
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      const category = await createCategory(token, {
        name,
        slug,
        description: description || null,
        parent_id: parentId ? Number(parentId) : null,
        status,
      });
      router.push(`/categories/${category.id}`);
    } catch (err) {
      setError(err instanceof CategoryApiError ? err.message : "Unable to create this category.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <button onClick={() => router.push("/categories")} className="mb-4 flex items-center gap-1 text-sm text-neutral-500 hover:text-primary-800">
        <Icon name="chevron-left" size={14} /> Back to categories
      </button>

      <PageHeader eyebrow="Catalog" title="Create category" />

      <form onSubmit={handleSubmit} className="rounded border border-neutral-200 bg-white p-6">
        <Field label="Name" required>
          <input
            required
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
        </Field>

        <Field label="Slug" required>
          <input
            required
            value={slug}
            onChange={(e) => { setSlugTouched(true); setSlug(e.target.value); }}
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm font-mono focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
        </Field>

        <Field label="Parent category" hint="Leave empty for a top-level category.">
          <select
            value={parentId}
            onChange={(e) => setParentId(e.target.value)}
            className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">No parent (top-level)</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </Field>

        <Field label="Description">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
        </Field>

        <Field label="Status">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm"
          >
            {CATEGORY_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </Field>

        <p className="mb-4 text-xs text-neutral-400">
          Image, display order, and featured state aren&apos;t supported on categories yet - there&apos;s no
          backend field for them.
        </p>

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
          {saving ? "Creating..." : "Create category"}
        </button>
      </form>
    </div>
  );
}

function Field({ label, required, hint, children }: { label: string; required?: boolean; hint?: string; children: React.ReactNode }) {
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
