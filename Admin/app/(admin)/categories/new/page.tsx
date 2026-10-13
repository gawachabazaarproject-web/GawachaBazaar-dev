"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  CATEGORY_STATUSES,
  CategoryApiError,
  CategoryRef,
  createCategory,
  fetchAdminCategories,
  uploadCategoryImage,
} from "@/lib/categories";
import { PageHeader } from "@/components/PageHeader";
import { Icon } from "@/components/icons";
import { BusyLabel } from "@/components/Spinner";

function slugify(value: string): string {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function NewCategoryForm() {
  const { getAccessToken } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [categories, setCategories] = useState<CategoryRef[]>([]);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [parentId, setParentId] = useState(searchParams.get("parent") ?? "");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("ACTIVE");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    fetchAdminCategories(token, { page: 1, page_size: 100 })
      .then((r) => setCategories(r.items.filter((c) => c.parent_id === null)))
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleNameChange = (value: string) => {
    setName(value);
    if (!slugTouched) setSlug(slugify(value));
  };

  const handleImage = (file: File | undefined) => {
    if (preview) URL.revokeObjectURL(preview);
    setImageFile(file ?? null);
    setPreview(file ? URL.createObjectURL(file) : null);
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
      if (imageFile) {
        // The category exists at this point - if only the photo fails,
        // land on its page (where the image can be retried) rather than
        // leaving the form open, which would create a duplicate on retry.
        await uploadCategoryImage(token, category.id, imageFile).catch(() => undefined);
      }
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

      <PageHeader
        eyebrow="Catalog"
        title={parentId ? "Create subcategory" : "Create category"}
        description={parentId ? "It appears inside its parent category on the app." : undefined}
      />

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

        <Field label="Parent category" hint="Leave empty for a top-level category (a shelf on the app). Pick one to make this a subcategory.">
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

        <Field label="Image" hint="Shown on the app. JPEG, PNG or WEBP, up to 8 MB.">
          <div className="flex items-center gap-3">
            {preview ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={preview} alt="" className="h-20 w-20 rounded object-cover" />
            ) : (
              <span className="flex h-20 w-20 items-center justify-center rounded bg-neutral-100 text-xs text-neutral-400">
                None
              </span>
            )}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => handleImage(e.target.files?.[0])}
              className="text-sm"
            />
          </div>
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
          {saving ? <BusyLabel>Creating...</BusyLabel> : "Create category"}
        </button>
      </form>
    </div>
  );
}

export default function NewCategoryPage() {
  return (
    <Suspense fallback={null}>
      <NewCategoryForm />
    </Suspense>
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
