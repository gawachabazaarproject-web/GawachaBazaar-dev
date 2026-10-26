"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  Category,
  CatalogApiError,
  fetchAdminProductDetail,
  fetchAdminProducts,
  fetchCategories,
  quickCreateProduct,
  ratePerBaseUnit,
  sizeLabel,
  uploadProductImage,
} from "@/lib/products";
import { amountUnits } from "@/lib/inventory";
import { parseSize, priceFromRate, RATE_LABEL, recall, remember, SIZE_CHIPS, slugPart, unitFamily } from "@/lib/product-form";
import { useWarehouses } from "@/lib/use-warehouses";
import { CategoryChecklist } from "@/components/CategoryChecklist";
import { ExpiryPicker, useExpiry } from "@/components/StockDialogs";
import { PageHeader } from "@/components/PageHeader";
import { Icon } from "@/components/icons";
import { BusyLabel } from "@/components/Spinner";
import { SearchableSelect, categoryOptions } from "@/components/SearchableSelect";

interface SizeRow {
  quantity: string;
  unit: string;
  /** Price of one whole pack. */
  price: string;
  sku: string;
}

const sizeKey = (s: { quantity: string; unit: string }) => `${Number(s.quantity)}-${s.unit}`;

const inputCls =
  "w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500";

/**
 * ADD PRODUCT: name, category, sizes with prices, first stock - one screen, one
 * save. The product, its sizes, prices and opening stock are saved together by
 * the server (all or nothing); only the optional photo is a second step, so a
 * photo problem can never leave a half-made product.
 */
export default function NewProductPage() {
  const { getAccessToken, user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const canReceive = !!(user && hasPermission(user.roles, "inventory.receive"));
  const canMedia = !!(user && hasPermission(user.roles, "products.manage_media"));
  const duplicating = !!searchParams.get("from");
  const { locations, defaultId } = useWarehouses(canReceive);

  const [categories, setCategories] = useState<Category[]>([]);
  const [name, setName] = useState("");
  const [categoryId, setCategoryId] = useState(searchParams.get("category") ?? "");
  const [extraCategoryIds, setExtraCategoryIds] = useState<number[]>([]);
  const [description, setDescription] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoProblem, setPhotoProblem] = useState<string | null>(null);
  const [sizes, setSizes] = useState<SizeRow[]>([]);
  const [customSize, setCustomSize] = useState("");
  const [customError, setCustomError] = useState<string | null>(null);
  const [showRate, setShowRate] = useState(false);
  const [rate, setRate] = useState("");
  const [stockAmount, setStockAmount] = useState("");
  const [stockUnit, setStockUnit] = useState("");
  const [locationId, setLocationId] = useState("");
  const [showMore, setShowMore] = useState(false);
  const [slug, setSlug] = useState("");
  const expiry = useExpiry();
  const [sameName, setSameName] = useState<{ id: number; name: string } | null>(null);

  const [saving, setSaving] = useState<null | "draft" | "publish" | "photo">(null);
  const [triedPublish, setTriedPublish] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ id: number; photoFailed: boolean } | null>(null);

  // ---- remembered choices, categories, and "duplicate product" ----
  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => undefined);
    const token = getAccessToken();
    const from = searchParams.get("from");
    if (from && token) {
      // Duplicate: same category, description, sizes and prices. Never the stock,
      // and it always starts as a draft.
      fetchAdminProductDetail(token, Number(from))
        .then((p) => {
          setCategoryId(String(p.category.id));
          setDescription(p.description ?? "");
          setSizes(
            p.variants
              .filter((v) => v.status === "ACTIVE")
              .map((v) => ({
                quantity: String(Number(v.quantity)),
                unit: v.unit,
                price: v.current_price ? String(Number(v.current_price.price)) : "",
                sku: "",
              })),
          );
        })
        .catch(() => undefined);
    } else {
      if (!searchParams.get("category")) {
        const last = recall<string>("lastCategory");
        if (last) setCategoryId(last);
      }
      const rows = (recall<string[]>("lastSizes") ?? [])
        .map(parseSize)
        .filter((s): s is NonNullable<ReturnType<typeof parseSize>> => s !== null)
        .map((s) => ({ ...s, price: "", sku: "" }));
      if (rows.length > 0) setSizes(rows);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!locationId && defaultId) setLocationId(defaultId);
  }, [defaultId, locationId]);

  // Warn when a product with the same name already exists.
  useEffect(() => {
    const text = name.trim();
    setSameName(null);
    if (text.length < 2) return;
    const timer = setTimeout(() => {
      const token = getAccessToken();
      if (!token) return;
      fetchAdminProducts(token, { q: text, page_size: 10 })
        .then((r) => {
          const hit = r.items.find((p) => p.name.trim().toLowerCase() === text.toLowerCase());
          setSameName(hit ? { id: hit.id, name: hit.name } : null);
        })
        .catch(() => undefined);
    }, 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name]);

  const photoPreview = useMemo(() => (photo ? URL.createObjectURL(photo) : null), [photo]);
  useEffect(() => () => { if (photoPreview) URL.revokeObjectURL(photoPreview); }, [photoPreview]);

  // ---- sizes ----
  const hasSize = (q: { quantity: string; unit: string }) => sizes.some((s) => sizeKey(s) === sizeKey(q));
  const toggleChip = (text: string) => {
    const parsed = parseSize(text);
    if (!parsed) return;
    setSizes((rows) =>
      rows.some((s) => sizeKey(s) === sizeKey(parsed))
        ? rows.filter((s) => sizeKey(s) !== sizeKey(parsed))
        : [...rows, { ...parsed, price: "", sku: "" }],
    );
  };
  const addCustomSize = () => {
    const parsed = parseSize(customSize);
    if (!parsed) {
      setCustomError('Type a size like "750 g", "1.5 kg", "12 pc" or "1 dozen".');
      return;
    }
    setCustomError(null);
    if (!hasSize(parsed)) setSizes((rows) => [...rows, { ...parsed, price: "", sku: "" }]);
    setCustomSize("");
  };
  const updateSize = (key: string, patch: Partial<SizeRow>) =>
    setSizes((rows) => rows.map((r) => (sizeKey(r) === key ? { ...r, ...patch } : r)));

  const firstFamily = sizes.map((s) => unitFamily(s.unit)).find((f) => f !== null) ?? null;
  const rateLabel = firstFamily ? RATE_LABEL[firstFamily] : null;
  const fillFromRate = () => {
    const value = Number(rate);
    if (!(value > 0)) return;
    setSizes((rows) => rows.map((r) => (unitFamily(r.unit) === firstFamily ? { ...r, price: priceFromRate(value, r.quantity, r.unit) } : r)));
  };

  // Stock is typed in kg / L / pieces; anything else (box, pack) is counted in packs.
  const stockSize = sizes.find((s) => firstFamily && unitFamily(s.unit) === firstFamily) ?? null;
  const stockUnits = stockSize ? amountUnits(stockSize.unit) : [];
  const effectiveStockUnit = stockUnits.some((u) => u.value === stockUnit) ? stockUnit : stockUnits[0]?.value ?? "";
  const stockLabel = stockUnits.find((u) => u.value === effectiveStockUnit)?.label ?? "packs";
  const stockNum = Number(stockAmount) > 0 ? Number(stockAmount) : 0;
  const wantsStock = canReceive && stockNum > 0;

  // ---- what stops a product being published ----
  const missing: { text: string; target: string }[] = [];
  if (!name.trim()) missing.push({ text: "Product name", target: "field-name" });
  if (!categoryId) missing.push({ text: "Category", target: "field-category" });
  if (sizes.length === 0) missing.push({ text: "At least one size", target: "field-sizes" });
  for (const s of sizes) {
    if (!(Number(s.price) > 0)) missing.push({ text: `Price for ${sizeLabel(s.quantity, s.unit)}`, target: `price-${sizeKey(s)}` });
  }
  if (wantsStock && !locationId) missing.push({ text: "A warehouse for the stock", target: "field-stock" });
  if (expiry.invalid) missing.push({ text: "Expiry date", target: "field-more" });
  const advice: string[] = [];
  if (!photo) advice.push("a photo");
  if (canReceive && !wantsStock) advice.push("stock");

  const goTo = (id: string) => {
    if (id === "field-more") setShowMore(true);
    window.setTimeout(() => {
      const el = document.getElementById(id);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
      (el?.querySelector("input,select,button") as HTMLElement | null)?.focus?.();
      if (el instanceof HTMLInputElement) el.focus();
    }, 0);
  };

  // Checked here so a bad file is explained before saving, not after.
  const choosePhoto = (file: File | null, input: HTMLInputElement) => {
    setPhotoProblem(null);
    if (file && !["image/jpeg", "image/png", "image/webp", "image/gif"].includes(file.type)) {
      setPhotoProblem("That file isn't a photo we can use. Choose a JPEG, PNG, WebP or GIF picture.");
      input.value = "";
      setPhoto(null);
      return;
    }
    if (file && file.size > 8 * 1024 * 1024) {
      setPhotoProblem("That photo is larger than 8 MB. Choose a smaller one.");
      input.value = "";
      setPhoto(null);
      return;
    }
    setPhoto(file);
  };

  const uploadPhoto = async (productId: number): Promise<boolean> => {
    const token = getAccessToken();
    if (!token || !photo || !canMedia) return true;
    try {
      await uploadProductImage(token, productId, photo, { altText: name.trim(), isPrimary: true });
      setPhotoProblem(null);
      return true;
    } catch (err) {
      setPhotoProblem(err instanceof CatalogApiError ? err.message : "The connection failed.");
      return false;
    }
  };

  const save = async (publish: boolean) => {
    const token = getAccessToken();
    if (!token) return;
    setTriedPublish(true);
    if (missing.length > 0) {
      goTo(missing[0].target);
      if (publish) return;
      // A draft only needs the basics.
      if (!name.trim() || !categoryId || sizes.length === 0) return;
      if (sizes.some((s) => !(Number(s.price) > 0))) return;
    }
    setSaving(publish ? "publish" : "draft");
    setError(null);
    try {
      const product = await quickCreateProduct(token, {
        category_id: Number(categoryId),
        name: name.trim(),
        slug: slug.trim() || undefined,
        description: description.trim() || null,
        status: publish ? "ACTIVE" : "DRAFT",
        extra_category_ids: extraCategoryIds.filter((id) => String(id) !== categoryId),
        sizes: sizes.map((s) => ({
          quantity: s.quantity,
          unit: s.unit,
          price: Number(s.price).toFixed(2),
          ...(s.sku.trim() ? { sku: s.sku.trim() } : {}),
        })),
        ...(wantsStock
          ? {
              stock: {
                location_id: Number(locationId),
                ...(stockSize
                  ? { amount: String(stockNum), amount_unit: effectiveStockUnit }
                  : { quantity: String(stockNum) }),
                ...(expiry.value ? { expiry_date: expiry.value } : {}),
              },
            }
          : {}),
      });
      remember("lastCategory", categoryId);
      remember("lastSizes", sizes.map((s) => sizeLabel(s.quantity, s.unit)));
      if (wantsStock) remember("lastWarehouse", locationId);

      if (photo && canMedia) {
        setSaving("photo");
        const ok = await uploadPhoto(product.id);
        if (!ok) {
          setCreated({ id: product.id, photoFailed: true });
          return;
        }
      }
      router.push(`/products/${product.id}?created=1`);
    } catch (err) {
      const reason = err instanceof CatalogApiError ? err.message : "The connection failed.";
      setError(`Couldn't save the product. ${reason} Nothing was saved - you can try again.`);
    } finally {
      setSaving(null);
    }
  };

  const retryPhoto = async () => {
    if (!created) return;
    setSaving("photo");
    const ok = await uploadPhoto(created.id);
    setSaving(null);
    if (ok) router.push(`/products/${created.id}?created=1`);
  };

  const showMissing = triedPublish && missing.length > 0;
  const busy = saving !== null;

  return (
    <div className="mx-auto max-w-2xl">
      <button type="button" onClick={() => router.push("/products")} className="mb-4 flex items-center gap-1 text-sm text-neutral-500 hover:text-primary-800">
        <Icon name="chevron-left" size={14} /> Back to products
      </button>

      <PageHeader eyebrow="Catalog" title="Add product" description="Name, sizes, prices and stock - saved together." />

      {duplicating && (
        <p className="mb-4 rounded border border-neutral-200 bg-white px-4 py-3 text-sm text-neutral-700">
          Copied from another product: category, sizes and prices. Give it a name and a photo. No stock is copied, and it is saved as a draft unless you publish it.
        </p>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          save(!duplicating);
        }}
        className="space-y-5 rounded border border-neutral-200 bg-white p-6"
      >
        <Field label="Product name" required id="field-name">
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={!!created}
            className={inputCls}
            placeholder="e.g. Fresh Tomatoes"
          />
          {sameName && (
            <p className="mt-1 text-xs text-status-warning">
              A product called &quot;{sameName.name}&quot; already exists.{" "}
              <Link href={`/products/${sameName.id}`} className="font-semibold underline">Open it</Link>
            </p>
          )}
        </Field>

        <Field label="Category" required id="field-category">
          <SearchableSelect value={categoryId} onChange={setCategoryId} placeholder="Choose a category" options={categoryOptions(categories)} disabled={!!created} />
        </Field>

        <Field label="Photo" hint={canMedia ? (photoProblem ?? "Optional. You can add it later.") : "You don't have permission to add photos."}>
          <div className="flex items-center gap-4">
            {photoPreview && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={photoPreview} alt="Preview" className="h-20 w-20 rounded border border-neutral-200 object-cover" />
            )}
            <input type="file" accept="image/*" disabled={!canMedia || !!created} onChange={(e) => choosePhoto(e.target.files?.[0] ?? null, e.target)} className="text-sm text-neutral-600" />
          </div>
        </Field>

        <Field label="Selling sizes" required hint="Tap the sizes you sell. Your last choice is remembered." id="field-sizes">
          <div className="flex flex-wrap gap-2">
            {SIZE_CHIPS.map((chip) => {
              const parsed = parseSize(chip)!;
              const on = hasSize(parsed);
              return (
                <button
                  key={chip}
                  type="button"
                  onClick={() => toggleChip(chip)}
                  disabled={!!created}
                  aria-pressed={on}
                  className={`min-h-[36px] rounded-full border px-3 py-1 text-sm font-medium ${
                    on ? "border-primary-700 bg-primary-800 text-white" : "border-neutral-300 text-neutral-700 hover:border-primary-500"
                  }`}
                >
                  {chip}
                </button>
              );
            })}
            {sizes
              .filter((s) => !SIZE_CHIPS.some((c) => sizeKey(parseSize(c)!) === sizeKey(s)))
              .map((s) => (
                <button
                  key={sizeKey(s)}
                  type="button"
                  onClick={() => setSizes((rows) => rows.filter((r) => sizeKey(r) !== sizeKey(s)))}
                  disabled={!!created}
                  className="min-h-[36px] rounded-full border border-primary-700 bg-primary-800 px-3 py-1 text-sm font-medium text-white"
                  title="Tap to remove"
                >
                  {sizeLabel(s.quantity, s.unit)} ×
                </button>
              ))}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <input
              value={customSize}
              onChange={(e) => { setCustomSize(e.target.value); setCustomError(null); }}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCustomSize(); } }}
              disabled={!!created}
              placeholder="Other size, e.g. 750 g"
              aria-label="Other size"
              className={`${inputCls} max-w-[200px]`}
            />
            <button type="button" onClick={addCustomSize} disabled={!!created || !customSize.trim()} className="text-sm font-medium text-primary-700 hover:underline disabled:opacity-40">
              Add
            </button>
          </div>
          {customError && <p className="mt-1 text-xs text-status-danger">{customError}</p>}
        </Field>

        {sizes.length > 0 && (
          <Field label="Prices" required>
            <div className="space-y-2">
              {sizes.map((s) => {
                const key = sizeKey(s);
                const per = Number(s.price) > 0 ? ratePerBaseUnit(s.price, s.quantity, s.unit) : null;
                const bad = triedPublish && !(Number(s.price) > 0);
                return (
                  <div key={key} id={`price-${key}`} className="flex items-center gap-3">
                    <span className="w-24 text-sm font-medium text-neutral-800">{sizeLabel(s.quantity, s.unit)}</span>
                    <span className="text-sm text-neutral-500">₹</span>
                    <input
                      type="number"
                      inputMode="decimal"
                      min="0"
                      step="0.01"
                      value={s.price}
                      onChange={(e) => updateSize(key, { price: e.target.value })}
                      disabled={!!created}
                      aria-label={`Price of ${sizeLabel(s.quantity, s.unit)}`}
                      aria-invalid={bad}
                      className={`w-28 rounded border px-2 py-1.5 text-sm ${bad ? "border-status-danger" : "border-neutral-300"}`}
                    />
                    <span className="text-xs text-neutral-400">{per ?? ""}</span>
                  </div>
                );
              })}
            </div>
            {rateLabel && sizes.length > 1 && !created && (
              <div className="mt-2">
                {!showRate ? (
                  <button type="button" onClick={() => setShowRate(true)} className="text-xs font-medium text-primary-700 hover:underline">
                    Set prices by rate per {rateLabel}
                  </button>
                ) : (
                  <div className="flex flex-wrap items-center gap-2 rounded bg-neutral-50 px-3 py-2 text-sm">
                    <span className="text-neutral-600">₹</span>
                    <input
                      type="number"
                      min="0"
                      step="any"
                      value={rate}
                      onChange={(e) => setRate(e.target.value)}
                      placeholder="60"
                      aria-label={`Rate per ${rateLabel}`}
                      className="w-24 rounded border border-neutral-300 px-2 py-1"
                    />
                    <span className="text-neutral-600">per {rateLabel}</span>
                    <button type="button" onClick={fillFromRate} disabled={!(Number(rate) > 0)} className="text-sm font-semibold text-primary-700 hover:underline disabled:opacity-40">
                      Fill prices
                    </button>
                    <span className="text-xs text-neutral-400">Rounded to the nearest ₹1 - you can still change each price.</span>
                  </div>
                )}
              </div>
            )}
          </Field>
        )}

        {canReceive && sizes.length > 0 && (
          <Field
            label="Initial stock"
            hint={`Optional. Typing an amount adds that stock to ${locations.find((l) => String(l.id) === locationId)?.name ?? "the warehouse"} as soon as you save. You can also add stock later.`}
            id="field-stock"
          >
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="number"
                inputMode="decimal"
                min="0"
                step="any"
                value={stockAmount}
                onChange={(e) => setStockAmount(e.target.value)}
                disabled={!!created}
                placeholder="e.g. 50"
                aria-label="Initial stock"
                className={`${inputCls} max-w-[140px]`}
              />
              {stockUnits.length > 0 ? (
                <select value={effectiveStockUnit} onChange={(e) => setStockUnit(e.target.value)} aria-label="Stock unit" className="rounded border border-neutral-300 bg-white px-2 py-2 text-sm">
                  {stockUnits.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
                </select>
              ) : (
                <span className="text-sm text-neutral-500">packs</span>
              )}
              {locations.length > 1 ? (
                <div className="min-w-[180px] flex-1">
                  <SearchableSelect
                    value={locationId}
                    onChange={setLocationId}
                    placeholder="Warehouse"
                    options={locations.map((l) => ({ value: String(l.id), label: l.name }))}
                  />
                </div>
              ) : locations.length === 1 ? (
                <span className="text-xs text-neutral-500">in {locations[0].name}</span>
              ) : null}
            </div>
          </Field>
        )}

        <div id="field-more">
          <button type="button" onClick={() => setShowMore((v) => !v)} aria-expanded={showMore} className="text-sm font-medium text-neutral-600 hover:text-primary-800">
            More details {showMore ? "▾" : "▸"}
          </button>
          {showMore && (
            <div className="mt-3 space-y-4 rounded border border-neutral-200 p-3">
              <Field label="Description">
                <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className={inputCls} />
              </Field>
              {wantsStock && <ExpiryPicker state={expiry} />}
              <Field label="Web address" hint="Made from the name; change only if needed.">
                <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder={slugPart(name) || "made-from-the-name"} className={`${inputCls} font-mono`} />
              </Field>
              <Field label="Also show in" hint="The product appears in these categories too.">
                <CategoryChecklist categories={categories} mainCategoryId={categoryId} selected={extraCategoryIds} onChange={setExtraCategoryIds} />
              </Field>
              {sizes.map((s) => (
                <Field key={sizeKey(s)} label={`Product code - ${sizeLabel(s.quantity, s.unit)}`}>
                  <input
                    value={s.sku}
                    onChange={(e) => updateSize(sizeKey(s), { sku: e.target.value })}
                    placeholder="Made for you"
                    className={`${inputCls} font-mono`}
                  />
                </Field>
              ))}
            </div>
          )}
        </div>

        {showMissing && !created && (
          <div role="alert" className="rounded border border-status-warning/40 bg-status-warningLight px-4 py-3 text-sm">
            <p className="mb-1 font-semibold text-neutral-800">Can&apos;t publish yet - missing:</p>
            <ul className="mb-2 list-disc pl-5 text-neutral-700">
              {missing.map((m) => <li key={m.text}>{m.text}</li>)}
            </ul>
            <button type="button" onClick={() => goTo(missing[0].target)} className="font-semibold text-primary-800 underline">Fix these</button>
          </div>
        )}

        {error && (
          <p role="alert" className="rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>
        )}

        {created ? (
          <div role="status" className="rounded border border-primary-200 bg-primary-50 px-4 py-3 text-sm text-primary-900">
            <p className="font-semibold">✓ The product was saved, but the photo couldn&apos;t be added.</p>
            {photoProblem && <p className="mb-2 text-neutral-700">{photoProblem} You can add the photo from the product page.</p>}
            <div className="flex gap-3">
              <button type="button" onClick={retryPhoto} disabled={busy} className="rounded bg-primary-800 px-3 py-1.5 font-semibold text-white disabled:opacity-50">
                {saving === "photo" ? "Uploading..." : "Try the photo again"}
              </button>
              <button type="button" onClick={() => router.push(`/products/${created.id}`)} className="font-semibold underline">Open the product</button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                disabled={busy}
                onClick={() => save(false)}
                className={`min-h-[44px] flex-1 rounded px-4 py-2.5 text-sm font-semibold disabled:opacity-60 ${
                  duplicating ? "bg-primary-800 text-white hover:bg-primary-700" : "border border-neutral-300 text-neutral-700 hover:bg-neutral-50"
                }`}
              >
                {saving === "draft" ? <BusyLabel>Saving...</BusyLabel> : "Save as draft"}
              </button>
              <button
                type={duplicating ? "button" : "submit"}
                onClick={duplicating ? () => save(true) : undefined}
                disabled={busy}
                className={`min-h-[44px] flex-1 rounded px-4 py-2.5 text-sm font-semibold disabled:opacity-60 ${
                  duplicating ? "border border-neutral-300 text-neutral-700 hover:bg-neutral-50" : "bg-primary-800 text-white hover:bg-primary-700"
                }`}
              >
                {saving === "publish" ? <BusyLabel>Saving...</BusyLabel> : saving === "photo" ? <BusyLabel>Adding photo...</BusyLabel> : "Save & publish"}
              </button>
            </div>
            {missing.length === 0 && advice.length > 0 && (
              <p className="text-xs text-neutral-400">You can publish now. Still to do later: {advice.join(" and ")}.</p>
            )}
          </>
        )}
      </form>
    </div>
  );
}

function Field({
  label,
  required,
  hint,
  id,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  id?: string;
  children: React.ReactNode;
}) {
  return (
    <div id={id}>
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">
        {label} {required && <span className="text-status-danger">*</span>}
      </label>
      {children}
      {hint && <p className="mt-1 text-xs text-neutral-400">{hint}</p>}
    </div>
  );
}
