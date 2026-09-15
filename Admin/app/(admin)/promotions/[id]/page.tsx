"use client";

import React, { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  CUSTOMER_SCOPES,
  DISCOUNT_TYPES,
  PromotionApiError,
  PromotionDetail,
  PromotionRedemptionRow,
  PromotionTargetInput,
  activatePromotion,
  disablePromotion,
  duplicatePromotion,
  fetchPromotionDetail,
  fetchPromotionRedemptions,
  pausePromotion,
  updatePromotion,
} from "@/lib/promotions";
import { AdminProductListItem, Category, fetchAdminProducts, fetchCategories } from "@/lib/products";
import { formatDateTime, formatMoney } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState } from "@/components/ErrorState";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Pagination } from "@/components/Pagination";
import { Icon } from "@/components/icons";

const inputClass = "w-full rounded border border-neutral-300 px-3 py-2 text-sm disabled:bg-neutral-50";

export default function PromotionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const promotionId = Number(id);
  const { getAccessToken, user } = useAuth();
  const router = useRouter();

  const [promotion, setPromotion] = useState<PromotionDetail | null>(null);
  const [redemptions, setRedemptions] = useState<{ items: PromotionRedemptionRow[]; page: number; page_size: number; total: number } | null>(null);
  const [redemptionsPage, setRedemptionsPage] = useState(1);
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<AdminProductListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<Record<string, string>>({});
  const [eligibleCustomerIdsText, setEligibleCustomerIdsText] = useState("");
  const [targetScope, setTargetScope] = useState<"ALL" | "PRODUCTS" | "CATEGORIES">("ALL");
  const [selectedProductIds, setSelectedProductIds] = useState<Set<number>>(new Set());
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<Set<number>>(new Set());
  const [isDirty, setIsDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [lifecycleAction, setLifecycleAction] = useState<"activate" | "pause" | "disable" | "duplicate" | null>(null);
  const [lifecycleLoading, setLifecycleLoading] = useState(false);
  const [lifecycleError, setLifecycleError] = useState<string | null>(null);

  const canEdit = user && hasPermission(user.roles, "promotions.update");
  const canManageStatus = user && hasPermission(user.roles, "promotions.manage_status");

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await fetchPromotionDetail(token, promotionId);
      setPromotion(detail);
      setForm({
        name: detail.name,
        description: detail.description ?? "",
        customer_title: detail.customer_title ?? "",
        customer_description: detail.customer_description ?? "",
        discount_value: detail.discount_value,
        max_discount_amount: detail.max_discount_amount ?? "",
        min_order_value: detail.min_order_value ?? "",
        min_quantity: detail.min_quantity ?? "",
        customer_scope: detail.customer_scope,
        priority: String(detail.priority),
        usage_limit_total: detail.usage_limit_total !== null ? String(detail.usage_limit_total) : "",
        usage_limit_per_customer: detail.usage_limit_per_customer !== null ? String(detail.usage_limit_per_customer) : "",
        starts_at: toLocalInputValue(detail.starts_at),
        ends_at: detail.ends_at ? toLocalInputValue(detail.ends_at) : "",
      });
      setEligibleCustomerIdsText(detail.eligible_customer_ids.join(", "));
      const productTargets = detail.targets.filter((t) => t.target_type === "PRODUCT").map((t) => t.target_id);
      const categoryTargets = detail.targets.filter((t) => t.target_type === "CATEGORY").map((t) => t.target_id);
      setSelectedProductIds(new Set(productTargets));
      setSelectedCategoryIds(new Set(categoryTargets));
      setTargetScope(productTargets.length > 0 ? "PRODUCTS" : categoryTargets.length > 0 ? "CATEGORIES" : "ALL");
      setIsDirty(false);
    } catch (err) {
      setError(err instanceof PromotionApiError ? err.message : "Unable to load this promotion.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [promotionId]);

  useEffect(() => {
    load();
    const token = getAccessToken();
    fetchCategories().then(setCategories).catch(() => undefined);
    if (token) fetchAdminProducts(token, { page: 1, page_size: 200 }).then((r) => setProducts(r.items)).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    fetchPromotionRedemptions(token, promotionId, redemptionsPage, 20).then(setRedemptions).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [promotionId, redemptionsPage]);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (isDirty) { e.preventDefault(); e.returnValue = ""; }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  const handleBack = () => {
    if (isDirty && !window.confirm("You have unsaved changes. Leave without saving?")) return;
    router.push("/promotions");
  };

  const updateField = (field: string, value: string) => {
    setForm((f) => ({ ...f, [field]: value }));
    setIsDirty(true);
  };

  const toggleProduct = (id: number) => {
    setSelectedProductIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
    setIsDirty(true);
  };
  const toggleCategory = (id: number) => {
    setSelectedCategoryIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
    setIsDirty(true);
  };

  const handleSave = async () => {
    const token = getAccessToken();
    if (!token || !promotion) return;
    setSaving(true);
    setFormError(null);
    try {
      const targets: PromotionTargetInput[] =
        targetScope === "PRODUCTS"
          ? Array.from(selectedProductIds).map((id) => ({ target_type: "PRODUCT" as const, target_id: id }))
          : targetScope === "CATEGORIES"
            ? Array.from(selectedCategoryIds).map((id) => ({ target_type: "CATEGORY" as const, target_id: id }))
            : [];
      const eligibleCustomerIds =
        form.customer_scope === "SPECIFIC"
          ? eligibleCustomerIdsText
              .split(",")
              .map((s) => Number(s.trim()))
              .filter((n) => Number.isFinite(n) && n > 0)
          : [];
      await updatePromotion(token, promotionId, {
        name: form.name,
        description: form.description || null,
        customer_title: form.customer_title || null,
        customer_description: form.customer_description || null,
        discount_value: Number(form.discount_value),
        max_discount_amount: form.max_discount_amount ? Number(form.max_discount_amount) : null,
        min_order_value: form.min_order_value ? Number(form.min_order_value) : null,
        min_quantity: form.min_quantity ? Number(form.min_quantity) : null,
        customer_scope: form.customer_scope,
        eligible_customer_ids: eligibleCustomerIds,
        priority: Number(form.priority) || 100,
        usage_limit_total: form.usage_limit_total ? Number(form.usage_limit_total) : null,
        usage_limit_per_customer: form.usage_limit_per_customer ? Number(form.usage_limit_per_customer) : null,
        starts_at: new Date(form.starts_at).toISOString(),
        ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null,
        targets,
      });
      await load();
    } catch (err) {
      setFormError(err instanceof PromotionApiError ? err.message : "Unable to save changes.");
    } finally {
      setSaving(false);
    }
  };

  const runLifecycleAction = async () => {
    const token = getAccessToken();
    if (!token || !lifecycleAction) return;
    setLifecycleLoading(true);
    setLifecycleError(null);
    try {
      if (lifecycleAction === "activate") await activatePromotion(token, promotionId);
      else if (lifecycleAction === "pause") await pausePromotion(token, promotionId);
      else if (lifecycleAction === "disable") await disablePromotion(token, promotionId);
      else if (lifecycleAction === "duplicate") {
        const copy = await duplicatePromotion(token, promotionId);
        setLifecycleAction(null);
        router.push(`/promotions/${copy.id}`);
        return;
      }
      setLifecycleAction(null);
      await load();
    } catch (err) {
      setLifecycleError(err instanceof PromotionApiError ? err.message : "Unable to complete this action.");
    } finally {
      setLifecycleLoading(false);
    }
  };

  if (loading) return <div className="animate-pulse text-sm text-neutral-400">Loading promotion...</div>;
  if (error || !promotion) return <ErrorState message={error ?? "Promotion not found."} onRetry={load} />;

  return (
    <div className="mx-auto max-w-4xl">
      <button onClick={handleBack} className="mb-4 flex items-center gap-1 text-sm text-neutral-500 hover:text-primary-800">
        <Icon name="chevron-left" size={14} /> Back to promotions
      </button>

      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-2xl font-semibold text-primary-900">{promotion.name}</h1>
            <StatusBadge status={promotion.effective_status} />
          </div>
          <p className="mt-1 text-sm text-neutral-500">
            {promotion.code ? <span className="font-mono">{promotion.code}</span> : "Automatic (no code)"} · created by {promotion.created_by_name}
          </p>
        </div>
        {canManageStatus && (
          <div className="flex shrink-0 gap-2">
            {promotion.admin_status !== "ACTIVE" && (
              <LifecycleButton label="Activate" onClick={() => setLifecycleAction("activate")} />
            )}
            {promotion.admin_status === "ACTIVE" && (
              <LifecycleButton label="Pause" onClick={() => setLifecycleAction("pause")} />
            )}
            {promotion.admin_status !== "DISABLED" && (
              <LifecycleButton label="Disable" danger onClick={() => setLifecycleAction("disable")} />
            )}
            <LifecycleButton label="Duplicate" onClick={() => setLifecycleAction("duplicate")} />
          </div>
        )}
      </div>

      <Section title="Performance">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Metric label="Redemptions" value={promotion.performance.redemption_count} />
          <Metric label="Reversed" value={promotion.performance.reversed_count} />
          <Metric label="Discount granted" value={formatMoney(promotion.performance.total_discount_granted)} />
          <Metric label="Avg order value" value={promotion.performance.average_order_value ? formatMoney(promotion.performance.average_order_value) : "—"} />
        </div>
        <p className="mt-3 text-xs text-neutral-400">
          &ldquo;Revenue influenced&rdquo; and average order value describe orders that redeemed this promotion - they are not a claim that the
          promotion caused that revenue.
        </p>
      </Section>

      <Section title="General">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Internal name">
            <input value={form.name ?? ""} onChange={(e) => updateField("name", e.target.value)} disabled={!canEdit} className={inputClass} />
          </Field>
          <Field label="Customer-facing title">
            <input value={form.customer_title ?? ""} onChange={(e) => updateField("customer_title", e.target.value)} disabled={!canEdit} className={inputClass} />
          </Field>
        </div>
        <Field label="Internal description">
          <textarea value={form.description ?? ""} onChange={(e) => updateField("description", e.target.value)} disabled={!canEdit} rows={2} className={inputClass} />
        </Field>
        <Field label="Customer-facing description">
          <textarea value={form.customer_description ?? ""} onChange={(e) => updateField("customer_description", e.target.value)} disabled={!canEdit} rows={2} className={inputClass} />
        </Field>
        <p className="mt-2 text-xs text-neutral-400">
          The coupon code and discount type cannot be changed after creation - duplicate this promotion to try a different one.
        </p>
      </Section>

      <Section title="Discount rules">
        <div className="grid grid-cols-2 gap-4">
          <Field label={promotion.discount_type === "PERCENTAGE" ? "Percentage (%)" : "Amount (₹)"}>
            <input type="number" min="0" step="0.01" value={form.discount_value ?? ""} onChange={(e) => updateField("discount_value", e.target.value)} disabled={!canEdit} className={inputClass} />
          </Field>
          <Field label="Max discount amount (₹)">
            <input type="number" min="0" step="0.01" value={form.max_discount_amount ?? ""} onChange={(e) => updateField("max_discount_amount", e.target.value)} disabled={!canEdit} className={inputClass} />
          </Field>
          <Field label="Minimum order value (₹)">
            <input type="number" min="0" step="0.01" value={form.min_order_value ?? ""} onChange={(e) => updateField("min_order_value", e.target.value)} disabled={!canEdit} className={inputClass} />
          </Field>
          <Field label="Minimum quantity">
            <input type="number" min="0" step="0.001" value={form.min_quantity ?? ""} onChange={(e) => updateField("min_quantity", e.target.value)} disabled={!canEdit} className={inputClass} />
          </Field>
        </div>
      </Section>

      <Section title="Applies to">
        <div className="mb-3 flex gap-2">
          {(["ALL", "PRODUCTS", "CATEGORIES"] as const).map((s) => (
            <button
              type="button"
              key={s}
              disabled={!canEdit}
              onClick={() => { setTargetScope(s); setIsDirty(true); }}
              className={`rounded border px-3 py-1.5 text-sm font-medium disabled:opacity-50 ${
                targetScope === s ? "border-primary-700 bg-primary-50 text-primary-800" : "border-neutral-300 text-neutral-600"
              }`}
            >
              {s === "ALL" ? "All products" : s === "PRODUCTS" ? "Specific products" : "Specific categories"}
            </button>
          ))}
        </div>
        {targetScope === "PRODUCTS" && (
          <div className="max-h-64 overflow-y-auto rounded border border-neutral-200">
            {products.map((p) => (
              <label key={p.id} className="flex cursor-pointer items-center gap-2 border-b border-neutral-100 px-3 py-2 text-sm last:border-b-0 hover:bg-neutral-50">
                <input type="checkbox" disabled={!canEdit} checked={selectedProductIds.has(p.id)} onChange={() => toggleProduct(p.id)} />
                <span className="flex-1 truncate">{p.name}</span>
                <span className="text-xs text-neutral-400">{p.category_name}</span>
              </label>
            ))}
          </div>
        )}
        {targetScope === "CATEGORIES" && (
          <div className="max-h-64 overflow-y-auto rounded border border-neutral-200">
            {categories.map((c) => (
              <label key={c.id} className="flex cursor-pointer items-center gap-2 border-b border-neutral-100 px-3 py-2 text-sm last:border-b-0 hover:bg-neutral-50">
                <input type="checkbox" disabled={!canEdit} checked={selectedCategoryIds.has(c.id)} onChange={() => toggleCategory(c.id)} />
                <span>{c.name}</span>
              </label>
            ))}
          </div>
        )}
      </Section>

      <Section title="Who is eligible">
        <Field label="Customer scope">
          <select value={form.customer_scope ?? "ALL"} onChange={(e) => updateField("customer_scope", e.target.value)} disabled={!canEdit} className={inputClass}>
            {CUSTOMER_SCOPES.map((s) => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}
          </select>
        </Field>
        {form.customer_scope === "SPECIFIC" && (
          <Field
            label="Eligible customer IDs"
            hint="Comma-separated user IDs. There is no customer directory in the admin panel yet, so IDs must be known already - see the Customers module for a given customer's ID."
          >
            <input
              value={eligibleCustomerIdsText}
              onChange={(e) => { setEligibleCustomerIdsText(e.target.value); setIsDirty(true); }}
              disabled={!canEdit}
              placeholder="e.g. 12, 45, 103"
              className={inputClass}
            />
          </Field>
        )}
      </Section>

      <Section title="Usage limits, priority & schedule">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Total usage limit" hint="Leave empty for unlimited.">
            <input type="number" min="1" value={form.usage_limit_total ?? ""} onChange={(e) => updateField("usage_limit_total", e.target.value)} disabled={!canEdit} className={inputClass} />
          </Field>
          <Field label="Per-customer usage limit" hint="Leave empty for unlimited.">
            <input type="number" min="1" value={form.usage_limit_per_customer ?? ""} onChange={(e) => updateField("usage_limit_per_customer", e.target.value)} disabled={!canEdit} className={inputClass} />
          </Field>
          <Field label="Priority">
            <input type="number" min="1" max="1000" value={form.priority ?? ""} onChange={(e) => updateField("priority", e.target.value)} disabled={!canEdit} className={inputClass} />
          </Field>
          <Field label="Redeemed so far">
            <input value={String(promotion.redemption_count)} disabled className={inputClass} />
          </Field>
          <Field label="Starts at">
            <input type="datetime-local" value={form.starts_at ?? ""} onChange={(e) => updateField("starts_at", e.target.value)} disabled={!canEdit} className={inputClass} />
          </Field>
          <Field label="Ends at">
            <input type="datetime-local" value={form.ends_at ?? ""} onChange={(e) => updateField("ends_at", e.target.value)} disabled={!canEdit} className={inputClass} />
          </Field>
        </div>

        {formError && (
          <p className="mt-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{formError}</p>
        )}
        {canEdit && (
          <button
            onClick={handleSave}
            disabled={!isDirty || saving}
            className="mt-3 rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {saving ? "Saving..." : "Save changes"}
          </button>
        )}
      </Section>

      <Section title={`Redemption history (${redemptions?.total ?? 0})`}>
        {!redemptions || redemptions.items.length === 0 ? (
          <p className="text-sm text-neutral-400">No redemptions yet.</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-neutral-200 text-xs uppercase tracking-wide text-neutral-500">
                  <tr>
                    <th className="py-2 font-medium">Order</th>
                    <th className="py-2 font-medium">Customer</th>
                    <th className="py-2 font-medium">Discount</th>
                    <th className="py-2 font-medium">Order total</th>
                    <th className="py-2 font-medium">Status</th>
                    <th className="py-2 font-medium">Redeemed</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {redemptions.items.map((r) => (
                    <tr key={r.id} className="hover:bg-neutral-50">
                      <td className="py-2">
                        <a href={`/orders/${r.order_id}`} className="font-mono text-xs text-primary-800 hover:underline">{r.order_number}</a>
                        <div><StatusBadge status={r.order_status} /></div>
                      </td>
                      <td className="py-2 text-neutral-700">{r.customer_name}</td>
                      <td className="py-2 text-neutral-700">{formatMoney(r.discount_amount)}</td>
                      <td className="py-2 text-neutral-700">{formatMoney(r.order_total)}</td>
                      <td className="py-2"><StatusBadge status={r.status} /></td>
                      <td className="py-2 text-neutral-500">{formatDateTime(r.redeemed_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={redemptions.page} pageSize={redemptions.page_size} total={redemptions.total} onPageChange={setRedemptionsPage} />
          </>
        )}
      </Section>

      <ConfirmDialog
        open={lifecycleAction !== null}
        title={lifecycleDialogCopy(lifecycleAction).title}
        description={lifecycleDialogCopy(lifecycleAction).description}
        confirmLabel={lifecycleDialogCopy(lifecycleAction).confirmLabel}
        danger={lifecycleAction === "disable"}
        loading={lifecycleLoading}
        error={lifecycleError}
        onConfirm={runLifecycleAction}
        onCancel={() => { setLifecycleAction(null); setLifecycleError(null); }}
      />
    </div>
  );
}

function toLocalInputValue(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function lifecycleDialogCopy(action: "activate" | "pause" | "disable" | "duplicate" | null) {
  switch (action) {
    case "activate":
      return {
        title: "Activate this promotion?",
        description: "Once active, it will be usable by eligible customers immediately (subject to its start/end dates). Double-check the discount amount, targets, and usage limits before activating.",
        confirmLabel: "Activate",
      };
    case "pause":
      return {
        title: "Pause this promotion?",
        description: "Paused promotions cannot be redeemed until reactivated. Existing orders that already used it are not affected.",
        confirmLabel: "Pause",
      };
    case "disable":
      return {
        title: "Disable this promotion?",
        description: "This is permanent - a disabled promotion can never be reactivated or reused. Orders that already redeemed it keep their historical discount unchanged.",
        confirmLabel: "Disable permanently",
      };
    case "duplicate":
      return {
        title: "Duplicate this promotion?",
        description: "Creates a new DRAFT promotion with the same rules, targets, and eligibility, but no coupon code and no accrued usage.",
        confirmLabel: "Duplicate",
      };
    default:
      return { title: "", description: "", confirmLabel: "Confirm" };
  }
}

function LifecycleButton({ label, danger, onClick }: { label: string; danger?: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`rounded border px-3 py-1.5 text-sm font-semibold ${
        danger ? "border-status-danger/40 text-status-danger hover:bg-status-dangerLight" : "border-primary-700 text-primary-800 hover:bg-primary-50"
      }`}
    >
      {label}
    </button>
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

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded border border-neutral-200 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">{label}</p>
      <p className="mt-1 font-display text-lg font-semibold text-primary-900">{value}</p>
    </div>
  );
}
