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
  fetchAdminCategories,
  fetchAdminCategoryDetail,
  fetchCategoryActivity,
  updateCategory,
} from "@/lib/categories";
import { AdminProductListItem, fetchAdminProducts, updateProduct } from "@/lib/products";
import { formatDateTime, formatMoney } from "@/lib/format";
import { ErrorState } from "@/components/ErrorState";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { Icon } from "@/components/icons";

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

  const canEdit = user && hasPermission(user.roles, "categories.update");

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

  const handleRestore = async () => {
    const token = getAccessToken();
    if (!token) return;
    await updateCategory(token, categoryId, { status: "ACTIVE" }).catch(() => undefined);
    load();
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

  if (loading) return <div className="animate-pulse text-sm text-neutral-400">Loading category...</div>;
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
          <div>
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
              disabled={!canEdit}
              className="w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm disabled:bg-neutral-50"
            >
              <option value="">No parent (top-level)</option>
              {allCategories.filter((c) => c.id !== categoryId).map((c) => (
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
            {savingGeneral ? "Saving..." : "Save changes"}
          </button>
        )}
      </Section>

      {category.children.length > 0 && (
        <Section title={`Subcategories (${category.children.length})`}>
          <div className="divide-y divide-neutral-100">
            {category.children.map((c) => (
              <div key={c.id} onClick={() => router.push(`/categories/${c.id}`)} className="flex cursor-pointer items-center justify-between py-2 text-sm hover:bg-neutral-50">
                <span className="text-neutral-800">{c.name}</span>
                <StatusBadge status={c.status} />
              </div>
            ))}
          </div>
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

      <Section title="Media, ordering & featured state">
        <p className="text-sm text-neutral-400">
          Categories don&apos;t have an image, display-order, or featured-state field in the backend yet - there is
          nothing real to control here until that model is extended.
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
