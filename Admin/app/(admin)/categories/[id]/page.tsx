"use client";

import React, { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  AdminCategoryDetail,
  CategoryActivityEntry,
  CategoryApiError,
  CATEGORY_STATUSES,
  CategoryRef,
  deleteCategory,
  deleteCategoryImage,
  fetchAdminCategories,
  fetchAdminCategoryDetail,
  fetchCategoryActivity,
  updateCategory,
  uploadCategoryImage,
} from "@/lib/categories";
import { AdminProductListItem, fetchAdminProducts, updateProduct } from "@/lib/products";
import { formatDateTime, formatMoney } from "@/lib/format";
import { ErrorState } from "@/components/ErrorState";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { ImageDropzone } from "@/components/ImageDropzone";
import { Icon } from "@/components/icons";
import { BusyLabel, PageLoader } from "@/components/Spinner";

export default function CategoryDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const categoryId = Number(id);
  const { getAccessToken, user } = useAuth();
  const router = useRouter();

  const [category, setCategory] = useState<AdminCategoryDetail | null>(null);
  const [allCategories, setAllCategories] = useState<CategoryRef[]>([]);
  const [activity, setActivity] = useState<CategoryActivityEntry[]>([]);
  const [products, setProducts] = useState<AdminProductListItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [general, setGeneral] = useState({ name: "", slug: "", parent_id: "", description: "", status: "" });
  const [savingGeneral, setSavingGeneral] = useState(false);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const canEdit = user && hasPermission(user.roles, "categories.update");
  const canCreate = user && hasPermission(user.roles, "categories.create");
  const canDelete = user && hasPermission(user.roles, "categories.delete");

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await fetchAdminCategoryDetail(token, categoryId);
      setCategory(detail);
      setGeneral({
        name: detail.name,
        slug: detail.slug,
        parent_id: detail.parent_id ? String(detail.parent_id) : "",
        description: detail.description ?? "",
        status: detail.status,
      });
      setIsDirty(false);
      fetchCategoryActivity(token, categoryId).then(setActivity).catch(() => undefined);
      fetchAdminProducts(token, { category_id: categoryId, page_size: 50 })
        .then((r) => setProducts(r.items))
        .catch(() => undefined);
    } catch (err) {
      setError(err instanceof CategoryApiError ? err.message : "Unable to load this category.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoryId]);

  useEffect(() => {
    load();
    const token = getAccessToken();
    if (token) fetchAdminCategories(token, { page: 1, page_size: 100 }).then((r) => setAllCategories(r.items)).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (isDirty) { e.preventDefault(); e.returnValue = ""; }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  const handleBack = () => {
    if (isDirty && !window.confirm("You have unsaved changes. Leave without saving?")) return;
    router.push("/categories");
  };

  const updateField = (field: keyof typeof general, value: string) => {
    setGeneral((g) => ({ ...g, [field]: value }));
    setIsDirty(true);
  };

  const handleSave = async () => {
    const token = getAccessToken();
    if (!token) return;
    setSavingGeneral(true);
    setGeneralError(null);
    try {
      await updateCategory(token, categoryId, {
        name: general.name,
        slug: general.slug,
        parent_id: general.parent_id ? Number(general.parent_id) : null,
        description: general.description || null,
        status: general.status,
      });
      await load();
    } catch (err) {
      setGeneralError(err instanceof CategoryApiError ? err.message : "Unable to save changes.");
    } finally {
      setSavingGeneral(false);
    }
  };

  const handleArchive = async () => {
    const token = getAccessToken();
    if (!token || !category) return;
    setArchiving(true);
    try {
      await updateCategory(token, categoryId, { status: "ARCHIVED" });
      setArchiveOpen(false);
      await load();
    } catch (err) {
      setGeneralError(err instanceof CategoryApiError ? err.message : "Unable to archive this category.");
    } finally {
      setArchiving(false);
    }
  };

  const handleDelete = async () => {
    const token = getAccessToken();
    if (!token) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteCategory(token, categoryId);
      router.push("/categories");
    } catch (err) {
      setDeleteError(err instanceof CategoryApiError ? err.message : "Unable to delete this category.");
      setDeleting(false);
    }
  };

  const handleRestore = async () => {
    const token = getAccessToken();
    if (!token) return;
    await updateCategory(token, categoryId, { status: "ACTIVE" }).catch(() => undefined);
    load();
  };

  const handleUploadImage = async (file: File) => {
    const token = getAccessToken();
    if (!token) return;
    try {
      await uploadCategoryImage(token, categoryId, file);
      await load();
    } catch (err) {
      throw new Error(err instanceof CategoryApiError ? err.message : "Unable to upload this image.");
    }
  };

  const handleRemoveImage = async () => {
    const token = getAccessToken();
    if (!token) return;
    try {
      await deleteCategoryImage(token, categoryId);
      await load();
    } catch (err) {
      throw new Error(err instanceof CategoryApiError ? err.message : "Unable to remove this image.");
    }
  };

  const handleMoveProduct = async (productId: number, newCategoryId: string) => {
    const token = getAccessToken();
    if (!token || !newCategoryId) return;
    await updateProduct(token, productId, { category_id: Number(newCategoryId) }).catch(() => undefined);
    // Reassignment changes this category's authoritative product_count
    // (shown in the header and in the archive-confirmation dialog), not
    // just which rows the Products section lists - reload the whole
    // detail so that count never goes stale after a move.
    await load();
  };

  if (loading) return <PageLoader label="Loading category..." />;
  if (error || !category) return <ErrorState message={error ?? "Category not found."} onRetry={load} />;

  return (
    <div className="mx-auto max-w-4xl">
      <button onClick={handleBack} className="mb-4 flex items-center gap-1 text-sm text-neutral-500 hover:text-primary-800">
        <Icon name="chevron-left" size={14} /> Back to categories
      </button>

      <div className="mb-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-2xl font-semibold text-primary-900">{category.name}</h1>
            <StatusBadge status={category.status} />
          </div>
          <p className="mt-1 text-sm text-neutral-500">
            {category.slug} · {category.product_count} product{category.product_count === 1 ? "" : "s"}
            {category.parent_name && ` · under ${category.parent_name}`}
          </p>
        </div>
        {canEdit && (
          <div className="flex items-center gap-2">
            {category.status !== "ARCHIVED" && (
              <button
                onClick={() => updateField("status", category.status === "ACTIVE" ? "INACTIVE" : "ACTIVE")}
                className="rounded border border-neutral-300 px-3 py-1.5 text-sm font-semibold text-neutral-700 hover:bg-neutral-50"
                title="Applied when you press Save changes"
              >
                {general.status === "ACTIVE" ? "Mark inactive" : "Mark active"}
              </button>
            )}
            {category.status === "ARCHIVED" ? (
              <button onClick={handleRestore} className="rounded border border-primary-700 px-3 py-1.5 text-sm font-semibold text-primary-800 hover:bg-primary-50">
                Restore
              </button>
            ) : (
              <button
                onClick={() => setArchiveOpen(true)}
                className="rounded border border-status-danger/40 px-3 py-1.5 text-sm font-semibold text-status-danger hover:bg-status-dangerLight"
              >
                Archive category
              </button>
            )}
            {canDelete && (
              <button
                onClick={() => { setDeleteError(null); setDeleteOpen(true); }}
                className="rounded bg-status-danger px-3 py-1.5 text-sm font-semibold text-white hover:bg-status-danger/90"
              >
                Delete
              </button>
            )}
          </div>
        )}
      </div>

      <Section title="General">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Name">
            <input
              value={general.name}
              onChange={(e) => updateField("name", e.target.value)}
              disabled={!canEdit}
              className="w-full rounded border border-neutral-300 px-3 py-2 text-sm disabled:bg-neutral-50"
            />
          </Field>
          <Field label="Slug">
            <input
              value={general.slug}
              onChange={(e) => updateField("slug", e.target.value)}
              disabled={!canEdit}
              className="w-full rounded border border-neutral-300 px-3 py-2 text-sm font-mono disabled:bg-neutral-50"
            />
          </Field>
          <Field label="Parent category">
            <select
              value={general.parent_id}
              onChange={(e) => updateField("parent_id", e.target.value)}
              disabled={!canEdit || category.children.length > 0}
              className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm disabled:bg-neutral-50"
            >
              <option value="">No parent (top-level)</option>
              {allCategories.filter((c) => c.id !== categoryId && c.parent_id === null).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Status">
            <select
              value={general.status}
              onChange={(e) => updateField("status", e.target.value)}
              disabled={!canEdit}
              className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm disabled:bg-neutral-50"
            >
              {CATEGORY_STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </Field>
          <div className="col-span-2">
            <Field label="Description">
              <textarea
                value={general.description}
                onChange={(e) => updateField("description", e.target.value)}
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
            onClick={handleSave}
            disabled={!isDirty || savingGeneral}
            className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {savingGeneral ? <BusyLabel>Saving...</BusyLabel> : "Save changes"}
          </button>
        )}
      </Section>

      {category.parent_id === null && (
        <Section title={`Subcategories (${category.children.length})`}>
          {category.children.length === 0 ? (
            <p className="mb-3 text-sm text-neutral-400">
              No subcategories yet. Add some to split this category into sections on the app.
            </p>
          ) : (
            <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {category.children.map((c) => (
                <div
                  key={c.id}
                  onClick={() => router.push(`/categories/${c.id}`)}
                  className="flex cursor-pointer items-center gap-3 rounded border border-neutral-200 p-2 text-sm hover:bg-neutral-50"
                >
                  {c.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={c.image_url} alt="" className="h-12 w-12 rounded object-cover" />
                  ) : (
                    <span className="h-12 w-12 rounded bg-neutral-100" />
                  )}
                  <span className="min-w-0 flex-1 truncate font-medium text-neutral-800">{c.name}</span>
                  <StatusBadge status={c.status} />
                </div>
              ))}
            </div>
          )}
          {canCreate && (
            <button
              onClick={() => router.push(`/categories/new?parent=${category.id}`)}
              className="rounded border border-primary-700 px-3 py-1.5 text-sm font-semibold text-primary-800 hover:bg-primary-50"
            >
              + Add subcategory
            </button>
          )}
        </Section>
      )}

      <Section title={`Products (${products?.length ?? 0})`}>
        {!products || products.length === 0 ? (
          <EmptyState icon="tag" title="No products in this category" message="Assign products from the Products module or move them here." />
        ) : (
          <div className="divide-y divide-neutral-100">
            {products.map((p) => (
              <div key={p.id} className="flex items-center justify-between py-2 text-sm">
                <a href={`/products/${p.id}`} className="min-w-0 flex-1 truncate font-medium text-primary-900 hover:underline">
                  {p.name}
                </a>
                <span className="mx-3 text-neutral-600">{p.price ? formatMoney(p.price, p.currency ?? "INR") : "—"}</span>
                <StatusBadge status={p.status} />
                {canEdit && (
                  <select
                    defaultValue=""
                    onChange={(e) => handleMoveProduct(p.id, e.target.value)}
                    className="ml-3 rounded border border-neutral-300 bg-white px-2 py-1 text-xs"
                  >
                    <option value="" disabled>Move to...</option>
                    {allCategories.filter((c) => c.id !== categoryId).map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="Image">
        {canEdit ? (
          <ImageDropzone
            currentUrl={category.image_url}
            onUpload={handleUploadImage}
            onRemove={category.image_url ? handleRemoveImage : undefined}
          />
        ) : category.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={category.image_url} alt="" className="max-h-40 rounded object-contain" />
        ) : (
          <p className="text-sm text-neutral-400">No image set.</p>
        )}
        <p className="mt-3 text-xs text-neutral-400">
          Shown on the app. Use a bright, well-lit photo - it is cropped to a square on category cards.
        </p>
      </Section>

      <Section title="Activity">
        {activity.length === 0 ? (
          <p className="text-sm text-neutral-400">No recorded activity yet.</p>
        ) : (
          <div className="space-y-2">
            {activity.map((entry) => (
              <div key={entry.id} className="flex items-start justify-between text-sm">
                <p className="text-neutral-800">
                  {entry.previous_state && entry.new_state
                    ? `${entry.action} — ${entry.previous_state} → ${entry.new_state}`
                    : entry.action}{" "}
                  <span className="text-neutral-400">by {entry.admin_name}</span>
                </p>
                <p className="shrink-0 text-xs text-neutral-400">{formatDateTime(entry.created_at)}</p>
              </div>
            ))}
          </div>
        )}
      </Section>

      <ConfirmDialog
        open={archiveOpen}
        title="Archive this category?"
        description={
          category.product_count > 0
            ? `${category.product_count} product${category.product_count === 1 ? " is" : "s are"} currently assigned to this category. Archiving hides the category from customer discovery, but does not move, hide, or delete its products - they keep this category until reassigned. The category itself cannot be deleted while products reference it.`
            : "This category has no products assigned. Archiving hides it from customer discovery - it can be restored at any time."
        }
        confirmLabel="Archive category"
        danger
        loading={archiving}
        onConfirm={handleArchive}
        onCancel={() => setArchiveOpen(false)}
      />

      <ConfirmDialog
        open={deleteOpen}
        title={`Delete "${category.name}"?`}
        description={
          category.product_count > 0 || category.children.length > 0
            ? "This category still has products or subcategories, so it can't be deleted yet. Move them first, or set it to Inactive to hide it from customers."
            : "This permanently removes the category. This can't be undone - set it to Inactive instead if you may want it back."
        }
        confirmLabel="Delete category"
        danger
        loading={deleting}
        error={deleteError}
        onConfirm={handleDelete}
        onCancel={() => setDeleteOpen(false)}
      />
    </div>
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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</label>
      {children}
    </div>
  );
}
