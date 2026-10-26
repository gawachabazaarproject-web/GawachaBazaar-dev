"use client";

import React, { use, useCallback, useEffect, useState, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import {
  AdminProductDetail,
  Category,
  CatalogApiError,
  createPrice,
  createVariant,
  deleteImage,
  deleteProduct,
  deleteVariant,
  fetchAdminProductDetail,
  fetchCategories,
  fetchProductActivity,
  PRODUCT_STATUSES,
  ratePerBaseUnit,
  sizeLabel,
  ProductActivityEntry,
  updateImage,
  updateProduct,
  updateVariant,
  uploadProductImage,
  VARIANT_UNITS,
} from "@/lib/products";
import { formatDateTime, formatMoney } from "@/lib/format";
import { ErrorState } from "@/components/ErrorState";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ImageDropzone } from "@/components/ImageDropzone";
import { packCount } from "@/lib/inventory";
import { CategoryChecklist } from "@/components/CategoryChecklist";
import { ReserveLevelEditor } from "@/components/ReserveLevelEditor";
import { ProductAlertEditor } from "@/components/ProductAlertEditor";
import { statusLabel } from "@/lib/product-form";
import {
  AddStockDialog,
  CorrectStockDialog,
  MoveStockDialog,
  RemoveStockAmountDialog,
} from "@/components/StockDialogs";
import { StockActionBanner, StockNotice } from "@/components/StockActionBanner";
import { checkReadiness, FixTarget, Readiness } from "@/lib/readiness";
import {
  expiryPhrase,
  fetchProductStockCard,
  plain,
  ProductStockItem,
  ProductStockOperation,
  stockErrorMessage,
} from "@/lib/inventory";
import { useWarehouses } from "@/lib/use-warehouses";
import { Icon } from "@/components/icons";
import { BusyLabel, PageLoader } from "@/components/Spinner";
import { SearchableSelect, categoryOptions } from "@/components/SearchableSelect";

export default function ProductDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const productId = Number(id);
  const { getAccessToken, user } = useAuth();
  const router = useRouter();

  const [product, setProduct] = useState<AdminProductDetail | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [activity, setActivity] = useState<ProductActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);
  // After the first load, refreshes are silent so the page does not blank out.
  const loadedOnce = useRef(false);
  const [error, setError] = useState<string | null>(null);

  const [extraIds, setExtraIds] = useState<number[]>([]);
  const [general, setGeneral] = useState({ name: "", slug: "", category_id: "", description: "", status: "" });
  const [savingGeneral, setSavingGeneral] = useState(false);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);

  const canEdit = user && hasPermission(user.roles, "products.update");
  const canDelete = user && hasPermission(user.roles, "products.delete");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const searchParams = useSearchParams();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const [fix, setFix] = useState<FixTarget | null>(null);
  const [statusBusy, setStatusBusy] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const canSetStockLevels = !!(user && hasPermission(user.roles, "inventory.adjust"));
  const canManageMedia = user && hasPermission(user.roles, "products.manage_media");
  const canManagePricing = user && hasPermission(user.roles, "products.manage_pricing");

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    if (!loadedOnce.current) setLoading(true); // refreshes after an edit stay in place
    setError(null);
    try {
      const detail = await fetchAdminProductDetail(token, productId);
      setProduct(detail);
      setGeneral({
        name: detail.name,
        slug: detail.slug,
        category_id: String(detail.category.id),
        description: detail.description ?? "",
        status: detail.status,
      });
      setExtraIds(detail.extra_categories.map((c) => c.id));
      setIsDirty(false);
      fetchProductActivity(token, productId).then(setActivity).catch(() => undefined);
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to load this product.");
    } finally {
      setLoading(false);
      loadedOnce.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  useEffect(() => {
    load();
    fetchCategories().then(setCategories).catch(() => undefined);
  }, [load]);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menuOpen]);

  // Arriving from a "Fix now" link on the products list (?price=ID or ?fix=...).
  const arrivedFix = useRef(false);
  useEffect(() => {
    if (!product || arrivedFix.current) return;
    arrivedFix.current = true;
    const priceId = Number(searchParams.get("price"));
    const wanted = searchParams.get("fix");
    if (priceId) setFix({ type: "price", variantId: priceId });
    else if (wanted === "price") setFix({ type: "price", variantId: 0 });
    else if (wanted === "size" || wanted === "stock" || wanted === "photo") setFix({ type: wanted });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product]);

  // "Fix now" scrolls to the control that fixes it.
  useEffect(() => {
    if (!fix) return;
    const id = fix.type === "photo" ? "media-section" : fix.type === "stock" ? "stock-section" : "sizes-section";
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [fix]);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  const handleDelete = async () => {
    const token = getAccessToken();
    if (!token) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteProduct(token, productId);
      setIsDirty(false);
      router.push("/products");
    } catch (err) {
      setDeleteError(err instanceof CatalogApiError ? err.message : "Unable to delete this product.");
    } finally {
      setDeleting(false);
    }
  };

  const handleBack = () => {
    if (isDirty && !window.confirm("You have unsaved changes. Leave without saving?")) return;
    router.push("/products");
  };

  const updateGeneralField = (field: keyof typeof general, value: string) => {
    setGeneral((g) => ({ ...g, [field]: value }));
    setIsDirty(true);
  };

  const handleSaveGeneral = async () => {
    const token = getAccessToken();
    if (!token) return;
    setSavingGeneral(true);
    setGeneralError(null);
    try {
      await updateProduct(token, productId, {
        name: general.name,
        slug: general.slug,
        category_id: Number(general.category_id),
        extra_category_ids: extraIds.filter((id) => String(id) !== general.category_id),
        description: general.description || null,
        status: general.status,
      });
      await load();
    } catch (err) {
      setGeneralError(err instanceof CatalogApiError ? err.message : "Unable to save changes.");
    } finally {
      setSavingGeneral(false);
    }
  };

  if (loading) return <PageLoader label="Loading product..." />;
  if (error || !product) return <ErrorState message={error ?? "Product not found."} onRetry={load} />;

  const sizeOf = (variantId: number) => {
    const v = product.variants.find((x) => x.id === variantId);
    return v ? sizeLabel(v.quantity, v.unit) : "";
  };
  const primaryImage = product.images.find((i) => i.is_primary) ?? product.images[0];
  const readiness = checkReadiness({
    name: product.name,
    hasCategory: !!product.category,
    imageCount: product.images.length,
    variants: product.variants.map((v) => ({
      id: v.id,
      label: sizeLabel(v.quantity, v.unit),
      status: v.status,
      hasPrice: !!v.current_price,
    })),
    hasStock: product.variant_stock.some((v) => Number(v.available_quantity) > 0),
  });

  // Publishing needs a size and a price on every size; missing stock only shows as "needs attention".
  const changeStatus = async (next: string) => {
    const token = getAccessToken();
    if (!token) return;
    setStatusError(null);
    if (next === "ACTIVE") {
      const blocking = readiness.problems.filter((p) => p.key !== "stock");
      if (blocking.length > 0) {
        setStatusError(`Can't make this live yet: ${blocking.map((p) => p.text).join(", ")}.`);
        setFix(blocking[0].fix);
        return;
      }
    }
    setStatusBusy(true);
    try {
      await updateProduct(token, productId, { status: next });
      await load();
    } catch (err) {
      setStatusError(`Couldn't change this product. ${err instanceof CatalogApiError ? err.message : "The connection failed."} Nothing was changed.`);
    } finally {
      setStatusBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <button onClick={handleBack} className="mb-4 flex items-center gap-1 text-sm text-neutral-500 hover:text-primary-800">
        <Icon name="chevron-left" size={14} /> Back to products
      </button>

      <div className="mb-4 flex items-start gap-4">
        <div className="h-20 w-20 shrink-0 overflow-hidden rounded bg-neutral-100">
          {primaryImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={primaryImage.image_url} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center rounded border border-dashed border-neutral-300 text-center text-[11px] leading-tight text-neutral-400">
              No photo
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-display text-2xl font-semibold text-primary-900">{product.name}</h1>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                product.status === "ACTIVE" ? "bg-primary-100 text-primary-800" : "bg-neutral-100 text-neutral-600"
              }`}
            >
              {product.status === "ACTIVE" ? "Live ●" : statusLabel(product.status)}
            </span>
          </div>
          <p className="mt-1 text-sm text-neutral-500">{product.category.name}</p>
        </div>
        {canEdit && (
          <div className="relative flex shrink-0 items-center gap-2" ref={menuRef}>
            {product.status === "ACTIVE" ? (
              <button type="button" onClick={() => changeStatus("INACTIVE")} disabled={statusBusy} className="min-h-[36px] rounded border border-neutral-300 px-3 py-1.5 text-sm font-semibold text-neutral-700 hover:bg-neutral-50 disabled:opacity-50">
                Hide from customers
              </button>
            ) : product.status !== "ARCHIVED" ? (
              <button type="button" onClick={() => changeStatus("ACTIVE")} disabled={statusBusy} className="min-h-[36px] rounded bg-primary-800 px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-700 disabled:opacity-50">
                {product.status === "DRAFT" ? "Publish" : "Make live"}
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label="More actions"
              className="min-h-[36px] rounded border border-neutral-300 px-3 py-1.5 text-sm font-semibold text-neutral-600 hover:bg-neutral-50"
            >
              ⋯
            </button>
            {menuOpen && (
              <div role="menu" className="absolute right-0 top-full z-20 mt-1 w-44 rounded border border-neutral-200 bg-white py-1 text-sm shadow-lg">
                <button role="menuitem" type="button" onClick={() => router.push(`/products/new?from=${product.id}`)} className="block w-full px-3 py-2 text-left hover:bg-neutral-50">Duplicate</button>
                {product.status !== "ARCHIVED" && (
                  <button role="menuitem" type="button" onClick={() => { setMenuOpen(false); changeStatus("ARCHIVED"); }} className="block w-full px-3 py-2 text-left hover:bg-neutral-50">Archive</button>
                )}
                {canDelete && (
                  <button role="menuitem" type="button" onClick={() => { setMenuOpen(false); setDeleteError(null); setDeleteOpen(true); }} className="block w-full px-3 py-2 text-left text-status-danger hover:bg-neutral-50">Delete…</button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {statusError && (
        <p role="alert" className="mb-4 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{statusError}</p>
      )}

      {searchParams.get("created") && (
        <p role="status" className="mb-4 rounded border border-primary-200 bg-primary-50 px-4 py-2.5 text-sm text-primary-900">
          ✓ {product.name} was added{product.status === "ACTIVE" ? " and is now live for customers." : " as a draft."}
        </p>
      )}

      <ReadinessCard readiness={readiness} onFix={setFix} />

      <div id="sizes-section">
        <VariantsSection product={product} canManagePricing={!!canManagePricing} canEdit={!!canEdit} canDelete={!!canDelete} fix={fix} onFixHandled={() => setFix(null)} onChange={load} />
      </div>

      <div id="stock-section">
        <StockSection product={product} fix={fix} onFixHandled={() => setFix(null)} onChange={load} />
      </div>

      <Section title="Details">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Name">
            <input
              value={general.name}
              onChange={(e) => updateGeneralField("name", e.target.value)}
              disabled={!canEdit}
              className="w-full rounded border border-neutral-300 px-3 py-2 text-sm disabled:bg-neutral-50"
            />
          </Field>
          <Field label="Category">
            <SearchableSelect
              value={general.category_id}
              onChange={(v) => v && updateGeneralField("category_id", v)}
              disabled={!canEdit}
              placeholder="Choose a category"
              options={categoryOptions(categories)}
            />
          </Field>
          <Field label="Also show in" hint="The product appears in these categories and subcategories too.">
            <CategoryChecklist
              categories={categories}
              mainCategoryId={general.category_id}
              selected={extraIds}
              onChange={(ids) => { setExtraIds(ids); setIsDirty(true); }}
              disabled={!canEdit}
            />
          </Field>
          <div className="col-span-2">
            <Field label="Description">
              <textarea
                value={general.description}
                onChange={(e) => updateGeneralField("description", e.target.value)}
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
            onClick={handleSaveGeneral}
            disabled={!isDirty || savingGeneral}
            className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {savingGeneral ? <BusyLabel>Saving...</BusyLabel> : "Save changes"}
          </button>
        )}
      </Section>

      <div id="media-section">
        <MediaSection product={product} canManageMedia={!!canManageMedia} onChange={load} />
      </div>

      <ConfirmDialog
        open={deleteOpen}
        title={`Delete "${product.name}"?`}
        description="This permanently removes the product with its variants, prices, photos and stock records. It can't be undone. Products that already appear in orders can't be deleted - archive those instead."
        confirmLabel="Delete product"
        danger
        loading={deleting}
        error={deleteError}
        onConfirm={handleDelete}
        onCancel={() => setDeleteOpen(false)}
      />

      <details className="mb-4 rounded border border-neutral-200 bg-white p-4">
        <summary className="cursor-pointer font-display text-base font-semibold text-primary-900">Advanced</summary>
        <div className="mt-4 space-y-5">
          <Field label="Web address (slug)" hint="Used in the product link. Change only if needed, then press Save changes above.">
            <input
              value={general.slug}
              onChange={(e) => updateGeneralField("slug", e.target.value)}
              disabled={!canEdit}
              className="w-full rounded border border-neutral-300 px-3 py-2 font-mono text-sm disabled:bg-neutral-50"
            />
          </Field>
          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-neutral-500">Low-stock level</h3>
            <ProductAlertEditor
              key={product.variant_stock.map((x) => `${x.variant_id}:${x.reserve_level ?? ""}`).join("|")}
              variants={product.variants}
              reserves={Object.fromEntries(product.variant_stock.map((x) => [x.variant_id, x.reserve_level]))}
              canEdit={canSetStockLevels}
              onSaved={load}
            />
          </div>
          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-neutral-500">Low-stock level per size</h3>
            <div className="divide-y divide-neutral-100">
              {product.variant_stock.map((vs) => (
                <div key={vs.variant_id} className="py-2 text-sm">
                  <div className="mb-1 flex items-center justify-between text-neutral-700">
                    <span>{sizeOf(vs.variant_id)} <span className="font-mono text-xs text-neutral-400">{vs.sku}</span></span>
                    <span className="text-neutral-500">{packCount(vs.available_quantity)} available</span>
                  </div>
                  <ReserveLevelEditor
                    key={`${vs.variant_id}-${vs.reserve_level ?? "default"}`}
                    variantId={vs.variant_id}
                    reserveLevel={vs.reserve_level}
                    effectiveReserve={vs.effective_reserve}
                    variantUnit={product.variants.find((v) => v.id === vs.variant_id)?.unit ?? "PACK"}
                    variantQuantity={product.variants.find((v) => v.id === vs.variant_id)?.quantity ?? "1"}
                    canEdit={canSetStockLevels}
                    onSaved={load}
                  />
                </div>
              ))}
            </div>
            <a href={`/inventory?q=${encodeURIComponent(product.name)}`} className="mt-2 inline-block text-sm font-semibold text-primary-700 hover:underline">
              Lots, batches and transfers in Inventory →
            </a>
          </div>
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">History</h3>
            {activity.length === 0 ? (
              <p className="text-sm text-neutral-400">No recorded activity yet.</p>
            ) : (
              <div className="space-y-2">
                {activity.map((entry) => (
                  <div key={`${entry.resource_type}-${entry.id}`} className="flex items-start justify-between text-sm">
                    <p className="text-neutral-800">
                      {formatActivityAction(entry)} <span className="text-neutral-400">by {entry.admin_name}</span>
                    </p>
                    <p className="shrink-0 text-xs text-neutral-400">{formatDateTime(entry.created_at)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </details>
    </div>
  );
}

function formatActivityAction(entry: ProductActivityEntry): string {
  if (entry.previous_state && entry.new_state) {
    return `${entry.action} — ${entry.previous_state} → ${entry.new_state}`;
  }
  if (entry.new_state) return `${entry.action} — ${entry.new_state}`;
  return entry.action;
}

function MediaSection({
  product,
  canManageMedia,
  onChange,
}: {
  product: AdminProductDetail;
  canManageMedia: boolean;
  onChange: () => void;
}) {
  const { getAccessToken } = useAuth();
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (file: File) => {
    const token = getAccessToken();
    if (!token) return;
    setError(null);
    try {
      await uploadProductImage(token, product.id, file, { isPrimary: product.images.length === 0 });
      onChange();
    } catch (err) {
      throw new Error(err instanceof CatalogApiError ? err.message : "Unable to upload this image.");
    }
  };

  const handleSetPrimary = async (imageId: number) => {
    const token = getAccessToken();
    if (!token) return;
    setError(null);
    try {
      await updateImage(token, imageId, { is_primary: true });
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to change the primary image.");
    }
    onChange();
  };

  const handleDelete = async (imageId: number) => {
    const token = getAccessToken();
    if (!token) return;
    setError(null);
    try {
      await deleteImage(token, imageId);
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to remove this image.");
    }
    onChange();
  };

  return (
    <Section title="Media">
      {product.images.length === 0 ? (
        <p className="mb-3 text-sm text-neutral-400">No images yet.</p>
      ) : (
        <div className="mb-4 flex flex-wrap gap-3">
          {product.images.map((img) => (
            <div key={img.id} className="w-28">
              <div className="relative h-28 w-28 overflow-hidden rounded border border-neutral-200 bg-neutral-100">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={img.image_url} alt={img.alt_text ?? ""} className="h-full w-full object-cover" />
                {img.is_primary && (
                  <span className="absolute left-1 top-1 rounded bg-primary-800 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                    Primary
                  </span>
                )}
              </div>
              {canManageMedia && (
                <div className="mt-1 flex justify-between text-xs">
                  {!img.is_primary && (
                    <button onClick={() => handleSetPrimary(img.id)} className="text-primary-700 hover:underline">
                      Set primary
                    </button>
                  )}
                  <button onClick={() => handleDelete(img.id)} className="ml-auto text-status-danger hover:underline">
                    Remove
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {canManageMedia && (
        <ImageDropzone label="Add an image" onUpload={handleUpload} />
      )}
      {error && <p className="mt-2 text-sm text-status-danger">{error}</p>}
    </Section>
  );
}

interface NewSize {
  unit: string;
  quantity: string;
  /** Price of one whole pack. */
  price: string;
}
const emptySize = (): NewSize => ({ unit: "KG", quantity: "", price: "" });

function VariantsSection({
  product,
  canManagePricing,
  canEdit,
  canDelete,
  fix,
  onFixHandled,
  onChange,
}: {
  product: AdminProductDetail;
  canManagePricing: boolean;
  canEdit: boolean;
  canDelete: boolean;
  fix: FixTarget | null;
  onFixHandled: () => void;
  onChange: () => void;
}) {
  const { getAccessToken } = useAuth();
  const [showAddVariant, setShowAddVariant] = useState(false);
  const [newSizes, setNewSizes] = useState<NewSize[]>([emptySize()]);
  const [sizesSaved, setSizesSaved] = useState<string | null>(null);
  const [addingVariant, setAddingVariant] = useState(false);
  const [rowMenu, setRowMenu] = useState<number | null>(null);
  const [cannotDelete, setCannotDelete] = useState<{ id: number; message: string } | null>(null);
  const activeSizes = product.variants.filter((v) => v.status === "ACTIVE").length;
  // Offer Delete only where it can work: not the only size of a live product, not a size holding stock.
  const mayOfferDelete = (v: AdminProductDetail["variants"][number]) =>
    canDelete &&
    !(product.status === "ACTIVE" && v.status === "ACTIVE" && activeSizes <= 1) &&
    !(Number(product.variant_stock.find((x) => x.variant_id === v.id)?.available_quantity ?? 0) > 0);
  // Inline price edit: the price being typed, and the last change (for Undo).
  const [pricingVariant, setPricingVariant] = useState<number | null>(null);
  const [priceDraft, setPriceDraft] = useState("");
  const [savingPrice, setSavingPrice] = useState(false);
  const [lastPriceChange, setLastPriceChange] = useState<{ variantId: number; label: string; from: string; to: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingVariant, setEditingVariant] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ unit: "KG", quantity: "" });
  const [savingEdit, setSavingEdit] = useState(false);
  const [deleteVariantId, setDeleteVariantId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  const filledSizes = newSizes.filter((n) => n.quantity.trim() || n.price.trim());
  const sizeProblems = filledSizes.map((n, i) => {
    if (!(Number(n.quantity) > 0) || !(Number(n.price) > 0)) return "Needs a pack size and a price above 0.";
    const dupExisting = product.variants.some((v) => v.unit === n.unit && Number(v.quantity) === Number(n.quantity));
    const dupInForm = filledSizes.some((m, j) => j < i && m.unit === n.unit && Number(m.quantity) === Number(n.quantity));
    if (dupExisting) return "This size already exists.";
    if (dupInForm) return "This size is listed twice.";
    return null;
  });
  const canSaveSizes = filledSizes.length > 0 && sizeProblems.every((p) => p === null);

  const handleAddSizes = async () => {
    const token = getAccessToken();
    if (!token || !canSaveSizes) return;
    setAddingVariant(true);
    setError(null);
    setSizesSaved(null);
    const done: string[] = [];
    try {
      for (const n of filledSizes) {
        const label = sizeLabel(n.quantity, n.unit);
        const sku = `${product.slug}-${label.replace(/[^a-z0-9]+/gi, "-")}`.toUpperCase();
        const created = await createVariant(token, product.id, {
          name: label,
          sku,
          unit: n.unit,
          quantity: n.quantity,
          status: "ACTIVE",
        });
        await createPrice(token, created.id, Number(n.price).toFixed(2));
        done.push(label);
        setNewSizes((rows) => rows.filter((r) => r !== n)); // saved ones leave the form
      }
      setSizesSaved(`Saved ${done.join(", ")}.`);
      setNewSizes([emptySize()]);
      setShowAddVariant(false);
      onChange();
    } catch (err) {
      const msg = err instanceof CatalogApiError ? err.message : "Unable to add these sizes.";
      setError(done.length > 0 ? `Saved ${done.join(", ")}. Then: ${msg}` : msg);
      if (done.length > 0) onChange();
    } finally {
      setAddingVariant(false);
    }
  };

  const handleToggleVariantStatus = async (variantId: number, currentStatus: string) => {
    const token = getAccessToken();
    if (!token) return;
    const next = currentStatus === "ACTIVE" ? "INACTIVE" : "ACTIVE";
    setError(null);
    try {
      await updateVariant(token, variantId, { status: next });
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to change this size.");
    }
    onChange();
  };

  const startEdit = (v: AdminProductDetail["variants"][number]) => {
    setEditingVariant(v.id);
    setEditForm({ unit: v.unit, quantity: String(Number(v.quantity)) });
    setError(null);
  };

  const handleSaveEdit = async () => {
    const token = getAccessToken();
    if (!token || editingVariant === null) return;
    setSavingEdit(true);
    setError(null);
    try {
      await updateVariant(token, editingVariant, {
        name: sizeLabel(editForm.quantity, editForm.unit),
        unit: editForm.unit,
        quantity: editForm.quantity,
      });
      setEditingVariant(null);
      onChange();
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to update this variant.");
    } finally {
      setSavingEdit(false);
    }
  };

  const handleConfirmDelete = async () => {
    const token = getAccessToken();
    if (!token || deleteVariantId === null) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteVariant(token, deleteVariantId);
      setDeleteVariantId(null);
      onChange();
    } catch (err) {
      const id = deleteVariantId;
      setDeleteVariantId(null);
      if (err instanceof CatalogApiError && err.status === 409) {
        setCannotDelete({ id, message: err.message });
      } else {
        setError(`Couldn't delete this size. ${err instanceof CatalogApiError ? err.message : "The connection failed."} Nothing was changed.`);
      }
    } finally {
      setDeleting(false);
    }
  };

  const variantToDelete = product.variants.find((v) => v.id === deleteVariantId);

  const startPriceEdit = (v: AdminProductDetail["variants"][number]) => {
    setPricingVariant(v.id);
    setPriceDraft(v.current_price ? String(Number(v.current_price.price)) : "");
    setError(null);
  };

  useEffect(() => {
    if (!fix) return;
    if (fix.type === "price" && canManagePricing) {
      const target =
        product.variants.find((v) => v.id === fix.variantId) ??
        product.variants.find((v) => v.status === "ACTIVE" && !v.current_price);
      if (target) startPriceEdit(target);
      onFixHandled();
    } else if (fix.type === "size" && canEdit) {
      setShowAddVariant(true);
      onFixHandled();
    } else if (fix.type === "price" || fix.type === "size") {
      onFixHandled();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fix]);

  const commitPrice = async (v: AdminProductDetail["variants"][number]) => {
    const token = getAccessToken();
    if (!token || savingPrice) return;
    const previous = v.current_price ? Number(v.current_price.price) : null;
    const next = Number(priceDraft);
    if (!(next > 0) || next === previous) {
      setPricingVariant(null);
      return;
    }
    setSavingPrice(true);
    setError(null);
    try {
      await createPrice(token, v.id, next.toFixed(2));
      setLastPriceChange(
        previous !== null
          ? { variantId: v.id, label: sizeLabel(v.quantity, v.unit), from: previous.toFixed(2), to: next.toFixed(2) }
          : null,
      );
      setPricingVariant(null);
      onChange();
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to update this price.");
    } finally {
      setSavingPrice(false);
    }
  };

  // Undo writes the old price as a new price - the history keeps both.
  const undoPrice = async () => {
    const token = getAccessToken();
    if (!token || !lastPriceChange) return;
    try {
      await createPrice(token, lastPriceChange.variantId, lastPriceChange.from);
      setLastPriceChange(null);
      onChange();
    } catch (err) {
      setError(err instanceof CatalogApiError ? err.message : "Unable to undo the price change.");
    }
  };

  return (
    <Section title="Selling options">
      <div className="divide-y divide-neutral-100">
        {product.variants.map((v) => {
          const hidden = v.status !== "ACTIVE";
          const unpriced = !hidden && !v.current_price;
          return (
            <div key={v.id} id={`size-${v.id}`} className={`flex flex-wrap items-center justify-between gap-2 py-2 text-sm ${hidden ? "opacity-60" : ""}`}>
              <div className="min-w-[110px]">
                <p className="font-medium text-neutral-800">
                  {sizeLabel(v.quantity, v.unit)}
                  {hidden && <span className="ml-2 rounded-full bg-neutral-100 px-2 py-0.5 text-xs font-semibold text-neutral-500">Hidden</span>}
                </p>
                <p className="text-xs text-neutral-500">
                  {v.current_price ? ratePerBaseUnit(v.current_price.price, v.quantity, v.unit) ?? "" : ""}
                </p>
              </div>
              <div className="flex items-center gap-1">
                {pricingVariant === v.id ? (
                  <>
                    <span className="text-neutral-500">₹</span>
                    <input
                      type="number"
                      inputMode="decimal"
                      min="0"
                      step="0.01"
                      autoFocus
                      value={priceDraft}
                      disabled={savingPrice}
                      onChange={(e) => setPriceDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitPrice(v);
                        if (e.key === "Escape") setPricingVariant(null);
                      }}
                      onBlur={() => commitPrice(v)}
                      aria-label={`Price of ${sizeLabel(v.quantity, v.unit)}`}
                      className="w-24 rounded border border-primary-500 px-2 py-1 text-sm"
                    />
                  </>
                ) : canManagePricing ? (
                  <button
                    type="button"
                    onClick={() => startPriceEdit(v)}
                    title="Click to change the price"
                    className={`min-h-[36px] rounded px-2 py-1 font-medium hover:bg-neutral-100 ${unpriced ? "text-status-danger" : "text-neutral-800"}`}
                  >
                    {v.current_price ? formatMoney(v.current_price.price, v.current_price.currency) : "Set price"}
                  </button>
                ) : (
                  <span className="px-2 py-1 font-medium text-neutral-800">
                    {v.current_price ? formatMoney(v.current_price.price, v.current_price.currency) : "No price set"}
                  </span>
                )}
              </div>
              {canEdit && (
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setRowMenu(rowMenu === v.id ? null : v.id)}
                    aria-haspopup="menu"
                    aria-expanded={rowMenu === v.id}
                    aria-label={`More for ${sizeLabel(v.quantity, v.unit)}`}
                    className="min-h-[36px] rounded px-2 text-lg leading-none text-neutral-500 hover:bg-neutral-100"
                  >
                    ⋯
                  </button>
                  {rowMenu === v.id && (
                    <div role="menu" className="absolute right-0 top-full z-20 mt-1 w-36 rounded border border-neutral-200 bg-white py-1 text-sm shadow-lg">
                      <button role="menuitem" type="button" onClick={() => { setRowMenu(null); startEdit(v); }} className="block w-full px-3 py-1.5 text-left hover:bg-neutral-50">Edit size</button>
                      <button role="menuitem" type="button" onClick={() => { setRowMenu(null); handleToggleVariantStatus(v.id, v.status); }} className="block w-full px-3 py-1.5 text-left hover:bg-neutral-50">
                        {v.status === "ACTIVE" ? "Hide" : "Show"}
                      </button>
                      {mayOfferDelete(v) && (
                        <button role="menuitem" type="button" onClick={() => { setRowMenu(null); setDeleteVariantId(v.id); }} className="block w-full px-3 py-1.5 text-left text-status-danger hover:bg-neutral-50">Delete…</button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {cannotDelete && (
        <div role="alert" className="mt-2 rounded border border-status-warning/40 bg-status-warningLight px-3 py-2 text-sm text-neutral-800">
          <p className="font-semibold">Can&apos;t delete this size.</p>
          <p>{cannotDelete.message}</p>
          <div className="mt-1 flex gap-4">
            <button
              type="button"
              onClick={() => {
                handleToggleVariantStatus(cannotDelete.id, "ACTIVE");
                setCannotDelete(null);
              }}
              className="font-semibold text-primary-800 underline"
            >
              Hide size
            </button>
            <button type="button" onClick={() => setCannotDelete(null)} className="text-neutral-500 hover:underline">Close</button>
          </div>
        </div>
      )}

      {lastPriceChange && (
        <p role="status" className="mt-2 rounded bg-primary-50 px-3 py-2 text-sm text-primary-900">
          {lastPriceChange.label}: ₹{lastPriceChange.from} → ₹{lastPriceChange.to}{" "}
          <button type="button" onClick={undoPrice} className="ml-2 font-semibold underline">Undo</button>
          <button type="button" onClick={() => setLastPriceChange(null)} className="ml-3 text-xs text-neutral-500 hover:underline">Dismiss</button>
        </p>
      )}

      {error && <p className="mt-2 text-sm text-status-danger">{error}</p>}

      {sizesSaved && <p className="mt-2 text-sm text-primary-800">{sizesSaved}</p>}

      {canEdit && (
        <div className="mt-3">
          {!showAddVariant ? (
            <button onClick={() => setShowAddVariant(true)} className="text-sm font-semibold text-primary-700 hover:underline">
              + Add new sizes
            </button>
          ) : (
            <div className="mt-2 rounded border border-neutral-200 p-3">
              <h3 className="mb-2 font-display text-sm font-semibold text-primary-900">Add new sizes</h3>
              <div className="space-y-2">
                {newSizes.map((n, i) => (
                  <div key={i} className="grid grid-cols-12 items-center gap-2">
                    <input
                      type="number"
                      min="0"
                      step="any"
                      placeholder="Pack size"
                      aria-label="Pack size"
                      value={n.quantity}
                      onChange={(e) => setNewSizes((rows) => rows.map((r, j) => (j === i ? { ...r, quantity: e.target.value } : r)))}
                      className="col-span-3 rounded border border-neutral-300 px-2 py-1.5 text-sm"
                    />
                    <select
                      value={n.unit}
                      aria-label="Unit"
                      onChange={(e) => setNewSizes((rows) => rows.map((r, j) => (j === i ? { ...r, unit: e.target.value } : r)))}
                      className="col-span-3 rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm"
                    >
                      {VARIANT_UNITS.map((u) => (
                        <option key={u} value={u}>{u}</option>
                      ))}
                    </select>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="₹ Price of this pack"
                      aria-label="Price of this pack"
                      value={n.price}
                      onChange={(e) => setNewSizes((rows) => rows.map((r, j) => (j === i ? { ...r, price: e.target.value } : r)))}
                      className="col-span-5 rounded border border-neutral-300 px-2 py-1.5 text-sm"
                    />
                    <button
                      type="button"
                      disabled={newSizes.length === 1}
                      onClick={() => setNewSizes((rows) => rows.filter((_, j) => j !== i))}
                      aria-label="Remove this row"
                      className="col-span-1 text-lg text-neutral-400 hover:text-status-danger disabled:opacity-30"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={() => setNewSizes((rows) => [...rows, emptySize()])}
                className="mt-2 text-sm font-medium text-primary-700 hover:underline"
              >
                + Add another size
              </button>

              {filledSizes.length > 0 && (
                <div className="mt-3 rounded border border-primary-200 bg-primary-50/40 p-3 text-sm">
                  <p className="mb-1 font-semibold text-primary-900">Review before saving</p>
                  <ul className="space-y-0.5">
                    {filledSizes.map((n, i) => (
                      <li key={i} className={sizeProblems[i] ? "text-status-danger" : "text-neutral-700"}>
                        {sizeProblems[i] ? (
                          <>
                            {Number(n.quantity) > 0 ? sizeLabel(n.quantity, n.unit) : "New size"} - {sizeProblems[i]}
                          </>
                        ) : (
                          <>
                            {sizeLabel(n.quantity, n.unit)} sells for ₹{Number(n.price).toFixed(2)}
                            {ratePerBaseUnit(n.price, n.quantity, n.unit) ? ` · ${ratePerBaseUnit(n.price, n.quantity, n.unit)}` : ""}
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="mt-3 flex gap-2">
                <button
                  onClick={handleAddSizes}
                  disabled={addingVariant || !canSaveSizes}
                  className="rounded bg-primary-800 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40"
                >
                  {addingVariant ? <BusyLabel>Saving...</BusyLabel> : filledSizes.length > 1 ? `Save ${filledSizes.length} sizes` : "Save size"}
                </button>
                <button
                  onClick={() => { setShowAddVariant(false); setNewSizes([emptySize()]); }}
                  className="rounded border border-neutral-300 px-3 py-1.5 text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <ConfirmDialog
        open={editingVariant !== null}
        title="Edit size"
        description="Change the amount or unit of this size. Its price and stock stay as they are."
        confirmLabel="Save"
        loading={savingEdit}
        onCancel={() => setEditingVariant(null)}
        onConfirm={handleSaveEdit}
      >
        <div className="mt-2 flex gap-2">
          <input
            type="number"
            min="0"
            step="any"
            value={editForm.quantity}
            onChange={(e) => setEditForm((f) => ({ ...f, quantity: e.target.value }))}
            placeholder="Amount (e.g. 250)"
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
          />
          <select
            value={editForm.unit}
            onChange={(e) => setEditForm((f) => ({ ...f, unit: e.target.value }))}
            className="rounded border border-neutral-300 bg-white px-3 py-2 text-sm"
          >
            {VARIANT_UNITS.map((u) => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
        </div>
      </ConfirmDialog>

      <ConfirmDialog
        open={deleteVariantId !== null}
        title="Delete this size?"
        description={`Permanently delete the ${variantToDelete ? sizeLabel(variantToDelete.quantity, variantToDelete.unit) : "selected"} size. This only works for a size that was just added by mistake: one with orders, stock, carts or a changed price is kept - hide it instead.`}
        confirmLabel="Delete size"
        loading={deleting}
        onCancel={() => setDeleteVariantId(null)}
        onConfirm={handleConfirmDelete}
      />

    </Section>
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

function ReadinessCard({ readiness, onFix }: { readiness: Readiness; onFix: (target: FixTarget) => void }) {
  const count = readiness.problems.length;
  return (
    <div
      className={`mb-4 rounded border p-4 ${
        readiness.ready ? "border-primary-200 bg-primary-50/50" : "border-status-warning/40 bg-status-warningLight/40"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className={`font-display text-base font-semibold ${readiness.ready ? "text-primary-800" : "text-status-warning"}`}>
          {readiness.ready ? "READY TO SELL" : `${count} ${count === 1 ? "THING NEEDS" : "THINGS NEED"} ATTENTION`}
        </p>
        {!readiness.ready && readiness.problems[0] && (
          <button
            type="button"
            onClick={() => onFix(readiness.problems[0].fix)}
            className="min-h-[36px] rounded bg-primary-800 px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-700"
          >
            Fix now
          </button>
        )}
      </div>
      <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
        {readiness.checks.map((c) => (
          <li key={c.key} className={c.ok ? "text-neutral-700" : c.advisory || c.waiting ? "text-neutral-500" : "text-status-danger"}>
            <span className="mr-1.5 inline-block w-4 text-center">{c.ok ? "✓" : c.advisory || c.waiting ? "○" : "✕"}</span>
            {c.label}
            {!c.ok && c.advisory && <span className="text-xs text-neutral-400"> (recommended)</span>}
          </li>
        ))}
      </ul>
      {readiness.problems.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-neutral-200/70 pt-2 text-sm">
          {readiness.problems.slice(0, 3).map((p) => (
            <li key={p.key} className="flex items-center justify-between gap-3">
              <span className="text-neutral-800">{p.text}</span>
              <button type="button" onClick={() => onFix(p.fix)} className="font-semibold text-primary-700 hover:underline">Fix</button>
            </li>
          ))}
          {readiness.problems.length > 3 && (
            <li className="text-neutral-500">…and {readiness.problems.length - 3} more - fix these first.</li>
          )}
        </ul>
      )}
    </div>
  );
}

/** Stock the way staff read it: how much, where, and the everyday actions. */
function StockSection({
  product,
  fix,
  onFixHandled,
  onChange,
}: {
  product: AdminProductDetail;
  fix: FixTarget | null;
  onFixHandled: () => void;
  onChange: () => void;
}) {
  const { user } = useAuth();
  const { locations } = useWarehouses(!!(user && hasPermission(user.roles, "inventory.transfer")));
  const can = (perm: Parameters<typeof hasPermission>[1]) => !!(user && hasPermission(user.roles, perm));
  const canReceive = can("inventory.receive");
  const canAdjust = can("inventory.adjust");
  const canReconcile = can("inventory.reconcile");
  const canMove = can("inventory.transfer") && locations.length > 1;
  const stock = product.stock;
  const hasSizes = product.variants.some((v) => v.status === "ACTIVE");
  const hasStock = !!stock && stock.warehouses.length > 0;

  const { getAccessToken } = useAuth();
  const [dialog, setDialog] = useState<"add" | "correct" | "remove" | "move" | null>(null);
  const [fresh, setFresh] = useState<ProductStockItem | null>(null);
  const [openError, setOpenError] = useState<string | null>(null);
  const [notice, setNotice] = useState<StockNotice | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  // Read the latest numbers right before a stock action (other staff and customers change them all day).
  const openDialog = async (kind: "add" | "correct" | "remove" | "move") => {
    const token = getAccessToken();
    if (!token) return;
    setOpenError(null);
    try {
      setFresh(await fetchProductStockCard(token, product.id));
      setDialog(kind);
    } catch (err) {
      setOpenError(stockErrorMessage(err, "load the latest stock", "Nothing was changed."));
    }
  };

  useEffect(() => {
    if (fix?.type === "stock") {
      if (canReceive && stock && hasSizes) openDialog("add");
      onFixHandled();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fix]);

  const done = (op: ProductStockOperation) => {
    setNotice({ message: op.message, operation: op.operation_id ? op : undefined });
    onChange();
  };
  const available = stock && stock.totals.length > 0 ? stock.totals.map((t) => `${plain(t.amount)} ${t.amount_unit}`).join(" + ") : null;
  const reserved = stock?.totals.filter((t) => Number(t.reserved_amount) > 0) ?? [];
  const expiring = stock?.expiry && stock.expiry.days_left <= 7 ? stock.expiry : null;

  return (
    <Section title="Stock">
      {notice && (
        <StockActionBanner
          notice={notice}
          historyHref={`/inventory?view=lot&q=${encodeURIComponent(product.name)}`}
          onChanged={() => onChange()}
          onDismiss={() => setNotice(null)}
        />
      )}
      {!stock || !hasSizes ? (
        <p className="text-sm text-neutral-500">Add a selling size first, then you can add stock.</p>
      ) : (
        <>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className={`font-display text-2xl font-semibold ${hasStock ? "text-primary-900" : "text-status-danger"}`}>
                {hasStock && available ? `${available} available` : "No stock yet"}
              </p>
              {reserved.map((t) => (
                <p key={t.family} className="text-sm text-neutral-500">
                  {plain(t.reserved_amount)} {t.amount_unit} reserved for orders
                </p>
              ))}
            </div>
            <div className="flex items-center gap-2">
              {canReceive && (
                <button type="button" onClick={() => openDialog("add")} className="min-h-[36px] rounded bg-primary-800 px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-700">
                  + Add stock
                </button>
              )}
              {hasStock && (canReconcile || canAdjust || canMove) && (
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setMenuOpen((o) => !o)}
                    aria-haspopup="menu"
                    aria-expanded={menuOpen}
                    aria-label="More stock actions"
                    className="min-h-[36px] rounded border border-neutral-300 px-3 py-1.5 text-sm font-semibold text-neutral-600 hover:bg-neutral-50"
                  >
                    ⋯
                  </button>
                  {menuOpen && (
                    <div role="menu" className="absolute right-0 top-full z-20 mt-1 w-48 rounded border border-neutral-200 bg-white py-1 text-sm shadow-lg">
                      {canReconcile && <button role="menuitem" type="button" onClick={() => { setMenuOpen(false); openDialog("correct"); }} className="block w-full px-3 py-2 text-left hover:bg-neutral-50">Correct stock count</button>}
                      {canAdjust && <button role="menuitem" type="button" onClick={() => { setMenuOpen(false); openDialog("remove"); }} className="block w-full px-3 py-2 text-left hover:bg-neutral-50">Remove stock</button>}
                      {canMove && <button role="menuitem" type="button" onClick={() => { setMenuOpen(false); openDialog("move"); }} className="block w-full px-3 py-2 text-left hover:bg-neutral-50">Move stock</button>}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          {stock.warehouses.length > 0 && (
            <ul className="mt-3 space-y-0.5 text-sm text-neutral-700">
              {stock.warehouses.map((w) => (
                <li key={`${w.location_id}-${w.family}`} className="flex justify-between border-b border-neutral-50 py-1 sm:max-w-sm">
                  <span>{w.location_name}</span>
                  <strong>{plain(w.amount)} {w.amount_unit}</strong>
                </li>
              ))}
            </ul>
          )}
          {expiring && (
            <p className="mt-3 text-sm text-status-warning">
              {plain(expiring.amount)} {expiring.amount_unit} · {expiryPhrase(expiring.days_left)}
            </p>
          )}
        </>
      )}
      {openError && <p role="alert" className="mt-3 text-sm text-status-danger">{openError}</p>}
      {stock && dialog === "add" && (
        <AddStockDialog product={fresh ?? stock} onClose={() => setDialog(null)} onDone={(message) => { setNotice({ message }); onChange(); }} />
      )}
      {stock && dialog === "correct" && <CorrectStockDialog product={fresh ?? stock} onClose={() => setDialog(null)} onDone={done} />}
      {stock && dialog === "remove" && <RemoveStockAmountDialog product={fresh ?? stock} onClose={() => setDialog(null)} onDone={done} />}
      {stock && dialog === "move" && <MoveStockDialog product={fresh ?? stock} onClose={() => setDialog(null)} onDone={done} />}
    </Section>
  );
}
