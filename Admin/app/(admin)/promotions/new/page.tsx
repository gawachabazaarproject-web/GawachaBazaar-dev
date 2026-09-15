"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  CreatePromotionPayload,
  CUSTOMER_SCOPES,
  DISCOUNT_TYPES,
  PromotionApiError,
  PromotionTargetInput,
  createPromotion,
} from "@/lib/promotions";
import { AdminProductListItem, Category, fetchAdminProducts, fetchCategories } from "@/lib/products";
import { PageHeader } from "@/components/PageHeader";
import { Icon } from "@/components/icons";

function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export default function NewPromotionPage() {
  const { getAccessToken } = useAuth();
  const router = useRouter();

  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<AdminProductListItem[]>([]);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [customerTitle, setCustomerTitle] = useState("");
  const [customerDescription, setCustomerDescription] = useState("");
  const [code, setCode] = useState("");
  const [discountType, setDiscountType] = useState<string>("PERCENTAGE");
  const [discountValue, setDiscountValue] = useState("");
  const [maxDiscountAmount, setMaxDiscountAmount] = useState("");
  const [minOrderValue, setMinOrderValue] = useState("");
  const [minQuantity, setMinQuantity] = useState("");
  const [customerScope, setCustomerScope] = useState("ALL");
  const [eligibleCustomerIds, setEligibleCustomerIds] = useState("");
  const [status, setStatus] = useState("DRAFT");
  const [priority, setPriority] = useState("100");
  const [usageLimitTotal, setUsageLimitTotal] = useState("");
  const [usageLimitPerCustomer, setUsageLimitPerCustomer] = useState("");
  const [startsAt, setStartsAt] = useState(toLocalInputValue(new Date()));
  const [endsAt, setEndsAt] = useState("");
  const [targetScope, setTargetScope] = useState<"ALL" | "PRODUCTS" | "CATEGORIES">("ALL");
  const [selectedProductIds, setSelectedProductIds] = useState<Set<number>>(new Set());
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<Set<number>>(new Set());

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    fetchCategories().then(setCategories).catch(() => undefined);
    if (token) fetchAdminProducts(token, { page: 1, page_size: 200 }).then((r) => setProducts(r.items)).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleProduct = (id: number) => {
    setSelectedProductIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };
  const toggleCategory = (id: number) => {
    setSelectedCategoryIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const percentageOverCap = discountType === "PERCENTAGE" && Number(discountValue) > 100;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = getAccessToken();
    if (!token) return;
    setError(null);

    if (targetScope === "PRODUCTS" && selectedProductIds.size === 0) {
      setError("Select at least one product, or switch scope to All products.");
      return;
    }
    if (targetScope === "CATEGORIES" && selectedCategoryIds.size === 0) {
      setError("Select at least one category, or switch scope to All products.");
      return;
    }
    if (customerScope === "SPECIFIC" && !eligibleCustomerIds.trim()) {
      setError("Enter at least one customer id for a specific-customer promotion.");
      return;
    }

    const targets: PromotionTargetInput[] =
      targetScope === "PRODUCTS"
        ? Array.from(selectedProductIds).map((id) => ({ target_type: "PRODUCT" as const, target_id: id }))
        : targetScope === "CATEGORIES"
          ? Array.from(selectedCategoryIds).map((id) => ({ target_type: "CATEGORY" as const, target_id: id }))
          : [];

    const eligibleIds =
      customerScope === "SPECIFIC"
        ? eligibleCustomerIds
            .split(",")
            .map((s) => Number(s.trim()))
            .filter((n) => Number.isFinite(n) && n > 0)
        : [];

    const payload: CreatePromotionPayload = {
      name,
      description: description || null,
      customer_title: customerTitle || null,
      customer_description: customerDescription || null,
      code: code || null,
      discount_type: discountType,
      discount_value: Number(discountValue),
      max_discount_amount: maxDiscountAmount ? Number(maxDiscountAmount) : null,
      min_order_value: minOrderValue ? Number(minOrderValue) : null,
      min_quantity: minQuantity ? Number(minQuantity) : null,
      customer_scope: customerScope,
      eligible_customer_ids: eligibleIds,
      status,
      priority: Number(priority) || 100,
      usage_limit_total: usageLimitTotal ? Number(usageLimitTotal) : null,
      usage_limit_per_customer: usageLimitPerCustomer ? Number(usageLimitPerCustomer) : null,
      starts_at: new Date(startsAt).toISOString(),
      ends_at: endsAt ? new Date(endsAt).toISOString() : null,
      targets,
    };

    setSaving(true);
    try {
      const promotion = await createPromotion(token, payload);
      router.push(`/promotions/${promotion.id}`);
    } catch (err) {
      setError(err instanceof PromotionApiError ? err.message : "Unable to create this promotion.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <button onClick={() => router.push("/promotions")} className="mb-4 flex items-center gap-1 text-sm text-neutral-500 hover:text-primary-800">
        <Icon name="chevron-left" size={14} /> Back to promotions
      </button>

      <PageHeader
        eyebrow="Marketing"
        title="Create promotion"
        description="Eligibility, discount amount, and usage limits are enforced by the backend on every checkout - this form only defines the rule."
      />

      <form onSubmit={handleSubmit} className="space-y-4">
        <Section title="Basics">
          <Field label="Internal name" required hint="Shown only in the admin panel.">
            <input required value={name} onChange={(e) => setName(e.target.value)} className={inputClass} />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Customer-facing title" hint="Shown to customers, e.g. on the cart/checkout screen.">
              <input value={customerTitle} onChange={(e) => setCustomerTitle(e.target.value)} className={inputClass} />
            </Field>
            <Field label="Coupon code" hint="Leave empty for an automatic discount (no code needed).">
              <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="e.g. GAWACHA20" className={`${inputClass} font-mono`} />
            </Field>
          </div>
          <Field label="Internal description">
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className={inputClass} />
          </Field>
          <Field label="Customer-facing description">
            <textarea value={customerDescription} onChange={(e) => setCustomerDescription(e.target.value)} rows={2} className={inputClass} />
          </Field>
        </Section>

        <Section title="Discount">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Discount type" required>
              <select value={discountType} onChange={(e) => setDiscountType(e.target.value)} className={inputClass}>
                {DISCOUNT_TYPES.map((t) => <option key={t} value={t}>{t === "PERCENTAGE" ? "Percentage off" : "Fixed amount off"}</option>)}
              </select>
            </Field>
            <Field label={discountType === "PERCENTAGE" ? "Percentage (%)" : "Amount (₹)"} required>
              <input required type="number" min="0" step="0.01" value={discountValue} onChange={(e) => setDiscountValue(e.target.value)} className={inputClass} />
              {percentageOverCap && <p className="mt-1 text-xs text-status-danger">A percentage discount cannot exceed 100.</p>}
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Max discount amount (₹)" hint="Caps a percentage discount. Optional.">
              <input type="number" min="0" step="0.01" value={maxDiscountAmount} onChange={(e) => setMaxDiscountAmount(e.target.value)} className={inputClass} />
            </Field>
            <Field label="Minimum order value (₹)" hint="Evaluated against the full cart. Optional.">
              <input type="number" min="0" step="0.01" value={minOrderValue} onChange={(e) => setMinOrderValue(e.target.value)} className={inputClass} />
            </Field>
          </div>
          <Field label="Minimum quantity" hint="Minimum quantity of targeted items. Optional.">
            <input type="number" min="0" step="0.001" value={minQuantity} onChange={(e) => setMinQuantity(e.target.value)} className={inputClass} />
          </Field>
        </Section>

        <Section title="Applies to">
          <div className="mb-3 flex gap-2">
            {(["ALL", "PRODUCTS", "CATEGORIES"] as const).map((s) => (
              <button
                type="button"
                key={s}
                onClick={() => setTargetScope(s)}
                className={`rounded border px-3 py-1.5 text-sm font-medium ${
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
                  <input type="checkbox" checked={selectedProductIds.has(p.id)} onChange={() => toggleProduct(p.id)} />
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
                  <input type="checkbox" checked={selectedCategoryIds.has(c.id)} onChange={() => toggleCategory(c.id)} />
                  <span>{c.name}</span>
                </label>
              ))}
            </div>
          )}
        </Section>

        <Section title="Who is eligible">
          <Field label="Customer scope" required>
            <select value={customerScope} onChange={(e) => setCustomerScope(e.target.value)} className={inputClass}>
              {CUSTOMER_SCOPES.map((s) => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}
            </select>
          </Field>
          {customerScope === "SPECIFIC" && (
            <Field label="Eligible customer IDs" hint="Comma-separated user IDs. There is no customer directory in the admin panel yet, so IDs must be known already.">
              <input value={eligibleCustomerIds} onChange={(e) => setEligibleCustomerIds(e.target.value)} placeholder="e.g. 12, 45, 103" className={inputClass} />
            </Field>
          )}
        </Section>

        <Section title="Usage limits & priority">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Total usage limit" hint="Leave empty for unlimited.">
              <input type="number" min="1" value={usageLimitTotal} onChange={(e) => setUsageLimitTotal(e.target.value)} className={inputClass} />
            </Field>
            <Field label="Per-customer usage limit" hint="Leave empty for unlimited.">
              <input type="number" min="1" value={usageLimitPerCustomer} onChange={(e) => setUsageLimitPerCustomer(e.target.value)} className={inputClass} />
            </Field>
          </div>
          <Field label="Priority" hint="When more than one automatic promotion could apply, the lowest priority number wins.">
            <input type="number" min="1" max="1000" value={priority} onChange={(e) => setPriority(e.target.value)} className={inputClass} />
          </Field>
        </Section>

        <Section title="Schedule & status">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Starts at" required>
              <input required type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} className={inputClass} />
            </Field>
            <Field label="Ends at" hint="Leave empty for no end date.">
              <input type="datetime-local" value={endsAt} onChange={(e) => setEndsAt(e.target.value)} className={inputClass} />
            </Field>
          </div>
          <Field label="Initial status">
            <select value={status} onChange={(e) => setStatus(e.target.value)} className={inputClass}>
              <option value="DRAFT">Draft (not visible or usable yet)</option>
              <option value="ACTIVE">Active (usable immediately, subject to schedule)</option>
            </select>
          </Field>
        </Section>

        {error && (
          <p className="rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>
        )}

        <button
          type="submit"
          disabled={saving}
          className="w-full rounded bg-primary-800 py-2.5 text-sm font-semibold text-white hover:bg-primary-700 disabled:opacity-60"
        >
          {saving ? "Creating..." : "Create promotion"}
        </button>
      </form>
    </div>
  );
}

const inputClass = "w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded border border-neutral-200 bg-white p-4">
      <h2 className="mb-3 font-display text-base font-semibold text-primary-900">{title}</h2>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

function Field({ label, required, hint, children }: { label: string; required?: boolean; hint?: string; children: React.ReactNode }) {
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
