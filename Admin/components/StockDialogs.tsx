"use client";

import React, { useEffect, useId, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { hasPermission } from "@/lib/permissions";
import { UNITS } from "@/lib/units";
import {
  amountText,
  convertAmount,
  correctProductStock,
  fetchProductStockCard,
  InventoryApiError,
  FAMILY_UNITS,
  moveProductStock,
  packCount,
  plain,
  ProductStockItem,
  ProductStockOperation,
  receiveStock,
  removeProductStock,
  setStockShares,
  stockErrorMessage,
  unitValueForLabel,
} from "@/lib/inventory";
import { remember } from "@/lib/product-form";
import { useWarehouses } from "@/lib/use-warehouses";
import { SearchableSelect } from "@/components/SearchableSelect";
import { BusyLabel } from "@/components/Spinner";

const inputCls =
  "w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500";
const labelCls = "mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500";

/** The measured unit family of a product's stock ("MASS" -> kg / g), if it has one. */
export function stockFamily(product: ProductStockItem): string | null {
  return product.totals.find((t) => FAMILY_UNITS[t.family])?.family ?? null;
}

const FAMILY_OF_PACK: Record<string, string> = Object.fromEntries(
  Object.entries(UNITS).filter(([, u]) => u.dimension === "MASS" || u.dimension === "VOLUME" || u.dimension === "COUNT").map(([k, u]) => [k, u.dimension]),
);

/**
 * After a refused stock action: if the numbers moved while the dialog was open
 * (someone else added, removed or sold stock) say exactly that, with the latest
 * figure, instead of a generic error. Otherwise the plain failure message.
 */
async function failureMessage(
  token: string,
  err: unknown,
  action: string,
  shown: ProductStockItem,
): Promise<{ message: string; latest: ProductStockItem | null }> {
  if (err instanceof InventoryApiError && (err.status === 409 || err.status === 422)) {
    try {
      const latest = await fetchProductStockCard(token, shown.product_id);
      const signature = (p: ProductStockItem) =>
        p.totals.map((t) => `${t.on_hand_amount}/${t.reserved_amount}`).join(",") +
        "|" +
        p.warehouses.map((w) => `${w.location_id}:${w.on_hand_amount}`).join(",");
      if (signature(latest) !== signature(shown)) {
        const available = latest.totals.map((t) => `${plain(t.amount)} ${t.amount_unit}`).join(" + ") || "0 kg";
        return {
          message: `Stock changed by another user. The latest available is ${available}. Nothing was changed - please review and try again.`,
          latest,
        };
      }
    } catch {
      /* fall through to the plain message */
    }
  }
  return { message: stockErrorMessage(err, action), latest: null };
}

// ---------------------------------------------------------------------------
// Shell
// ---------------------------------------------------------------------------

function DialogShell({
  title,
  subtitle,
  busy,
  onClose,
  onSubmit,
  submitLabel,
  submitDisabled,
  danger,
  error,
  children,
}: {
  title: string;
  subtitle?: React.ReactNode;
  busy: boolean;
  onClose: () => void;
  onSubmit: () => void;
  submitLabel: React.ReactNode;
  submitDisabled?: boolean;
  danger?: boolean;
  error?: string | null;
  children: React.ReactNode;
}) {
  const titleId = useId();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:px-4" onClick={() => !busy && onClose()}>
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          if (!busy && !submitDisabled) onSubmit();
        }}
        className="max-h-[92vh] w-full overflow-y-auto rounded-t-lg bg-white p-5 shadow-xl sm:max-w-md sm:rounded"
      >
        <h2 id={titleId} className="font-display text-lg font-semibold text-primary-900">{title}</h2>
        {subtitle ? <div className="mb-4 mt-0.5 text-sm text-neutral-500">{subtitle}</div> : <div className="mb-4" />}
        <div className="space-y-4">{children}</div>
        {error && (
          <p role="alert" className="mt-4 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">
            {error}
          </p>
        )}
        <div className="sticky bottom-0 -mx-5 mt-5 flex justify-end gap-2 border-t border-neutral-100 bg-white px-5 pb-1 pt-3">
          <button type="button" onClick={onClose} disabled={busy} className="rounded border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700 disabled:opacity-50">
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy || submitDisabled}
            className={`min-h-[40px] rounded px-4 py-2 text-sm font-semibold text-white disabled:opacity-40 ${danger ? "bg-status-danger" : "bg-primary-800 hover:bg-primary-700"}`}
          >
            {busy ? <BusyLabel>Working...</BusyLabel> : submitLabel}
          </button>
        </div>
      </form>
    </div>
  );
}

function AmountField({
  value,
  onValue,
  unit,
  onUnit,
  family,
  label,
  placeholder,
  autoFocus,
}: {
  value: string;
  onValue: (v: string) => void;
  unit: string;
  onUnit: (u: string) => void;
  family: string | null;
  label: string;
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const units = family ? FAMILY_UNITS[family] : [];
  return (
    <div>
      <label className={labelCls}>{label}</label>
      <div className="flex gap-2">
        <input
          type="number"
          inputMode="decimal"
          min="0"
          step="any"
          autoFocus={autoFocus}
          value={value}
          onChange={(e) => onValue(e.target.value)}
          placeholder={placeholder ?? "e.g. 50"}
          aria-label={label}
          className={inputCls}
        />
        {units.length > 0 ? (
          <select value={unit} onChange={(e) => onUnit(e.target.value)} aria-label="Unit" className="rounded border border-neutral-300 bg-white px-2 py-2 text-sm">
            {units.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
          </select>
        ) : (
          <span className="self-center text-sm text-neutral-500">packs</span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Expiry
// ---------------------------------------------------------------------------

const EXPIRY_CHOICES = [
  { value: "none", label: "No expiry" },
  { value: "2", label: "In 2 days" },
  { value: "3", label: "In 3 days" },
  { value: "5", label: "In 5 days" },
  { value: "7", label: "In 7 days" },
  { value: "date", label: "Pick a date" },
];

function isoDate(daysFromNow: number): string {
  const d = new Date();
  d.setDate(d.getDate() + daysFromNow);
  return d.toLocaleDateString("en-CA");
}

/** "Use within" choice -> the date to send ("" = none). */
export function useExpiry() {
  const [choice, setChoice] = useState("none");
  const [date, setDate] = useState("");
  const value = choice === "none" ? "" : choice === "date" ? date : isoDate(Number(choice));
  return { choice, setChoice, date, setDate, value, invalid: choice === "date" && !date };
}

export function ExpiryPicker({ state }: { state: ReturnType<typeof useExpiry> }) {
  return (
    <div>
      <label className={labelCls}>Expiry</label>
      <div className="flex gap-2">
        <select value={state.choice} onChange={(e) => state.setChoice(e.target.value)} aria-label="Expiry" className={`${inputCls} bg-white`}>
          {EXPIRY_CHOICES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        {state.choice === "date" && (
          <input type="date" min={isoDate(0)} value={state.date} onChange={(e) => state.setDate(e.target.value)} aria-label="Expiry date" className={inputCls} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add stock
// ---------------------------------------------------------------------------

/**
 * ADD STOCK: type how much arrived. Warehouse, delivery record, pack split and
 * the movement are the server's job; the dialog only previews what customers
 * will be able to buy.
 */
export function AddStockDialog({
  product,
  onClose,
  onDone,
}: {
  product: ProductStockItem;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const { getAccessToken, user } = useAuth();
  const canAssign = !!(user && hasPermission(user.roles, "inventory.adjust"));
  const { locations, defaultId } = useWarehouses();
  const family = stockFamily(product);
  const units = family ? FAMILY_UNITS[family] : [];
  const sizes = product.variants.filter((v) => family && FAMILY_OF_PACK[v.pack_unit] === family);
  const target = family ? sizes[0] : product.variants[0];

  const [amount, setAmount] = useState("");
  const [unit, setUnit] = useState(units[0]?.value ?? "");
  const [locationId, setLocationId] = useState("");
  const [more, setMore] = useState(false);
  const [notes, setNotes] = useState("");
  const [shares, setShares] = useState<Record<number, string>>({});
  const expiry = useExpiry();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!locationId && defaultId) setLocationId(defaultId);
  }, [defaultId, locationId]);

  const amountNum = Number(amount) > 0 ? Number(amount) : 0;
  const unitLabel = units.find((u) => u.value === unit)?.label ?? "packs";
  const shareSum = sizes.reduce((sum, v) => sum + (Number(shares[v.variant_id]) > 0 ? Number(shares[v.variant_id]) : 0), 0);
  const overShared = shareSum > amountNum + 0.0005;
  const locationName = locations.find((l) => String(l.id) === locationId)?.name;
  const currentTotal = product.totals.find((t) => t.family === family);
  const afterAmount =
    family && currentTotal && amountNum > 0
      ? Math.round((convertAmount(Number(currentTotal.amount), unitValueForLabel(family, currentTotal.amount_unit), unit, family) + amountNum) * 1000) / 1000
      : null;
  const afterText = afterAmount !== null ? `${plain(afterAmount)} ${unitLabel}` : null;
  // Same arithmetic as the server (stock_pool.py): a size sells whole packs of
  // (shared pool + what is kept for that size alone). This delivery goes into the
  // shared pool, except the part kept for one size below.
  const baseOf = (value: number, unitKey: string) => {
    const list = family ? FAMILY_UNITS[family] : [];
    const u = list.find((x) => x.value === unitKey || x.label === unitKey || (unitKey === "pcs" && x.value === "UNIT"));
    return Math.round(value * (u?.factor ?? 1));
  };
  const poolBefore = baseOf(Number(currentTotal?.unassigned_amount ?? 0), currentTotal?.amount_unit ?? unit);
  const poolAfter = poolBefore + baseOf(amountNum, unit) - baseOf(shareSum, unit);
  const packsAfter = (v: (typeof sizes)[number]) => {
    const own = baseOf(Number(v.share_amount), v.amount_unit) + baseOf(Number(shares[v.variant_id]) > 0 ? Number(shares[v.variant_id]) : 0, unit);
    const size = baseOf(Number(v.pack_quantity), v.pack_unit);
    return size > 0 ? Math.floor((Math.max(poolAfter, 0) + own) / size) : 0;
  };

  const submit = async () => {
    const token = getAccessToken();
    if (!token || !target) return;
    setBusy(true);
    setError(null);
    let received = false;
    try {
      remember("lastWarehouse", locationId);
      await receiveStock(token, {
        variant_id: target.variant_id,
        location_id: Number(locationId),
        ...(family ? { amount: String(amountNum), amount_unit: unit } : { quantity: String(amountNum) }),
        ...(expiry.value ? { expiry_date: expiry.value } : {}),
        ...(notes.trim() ? { remarks: notes.trim() } : {}),
      });
      received = true;
      const assigned = sizes
        .filter((v) => Number(shares[v.variant_id]) > 0)
        .map((v) => ({ variant_id: v.variant_id, amount: String(Number(shares[v.variant_id])), amount_unit: unit }));
      if (assigned.length > 0) await setStockShares(token, product.product_id, assigned, true);
      onDone(`Added ${plain(amountNum)} ${unitLabel} of ${product.product_name}`);
      onClose();
    } catch (err) {
      if (received) {
        onDone(`Added ${plain(amountNum)} ${unitLabel} of ${product.product_name}`);
        setError(
          `${stockErrorMessage(err, "reserve that stock for one size", "")}The stock itself was added; assign it later from "Sizes & sharing".`,
        );
      } else {
        setError(stockErrorMessage(err, "add stock"));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <DialogShell
      title={`Add stock - ${product.product_name}`}
      busy={busy}
      onClose={onClose}
      onSubmit={submit}
      submitLabel={amountNum > 0 ? `Add ${plain(amountNum)} ${unitLabel}` : "Add stock"}
      submitDisabled={!amountNum || !locationId || !target || overShared || expiry.invalid}
      error={error}
    >
      {!target ? (
        <p className="text-sm text-neutral-600">This product has no sizes yet. Add a size on the product page first.</p>
      ) : (
        <>
          <AmountField value={amount} onValue={setAmount} unit={unit} onUnit={setUnit} family={family} label="Amount received" autoFocus />

          {locations.length > 1 ? (
            <div>
              <label className={labelCls}>Warehouse</label>
              <SearchableSelect
                value={locationId}
                onChange={setLocationId}
                placeholder="Choose a warehouse"
                options={locations.map((l) => ({ value: String(l.id), label: l.name }))}
              />
            </div>
          ) : (
            <div>
              <label className={labelCls}>Warehouse</label>
              <p className="text-sm text-neutral-800">{locationName ?? "No active warehouse - add one first"}</p>
            </div>
          )}

          {family && sizes.length > 0 && amountNum > 0 && (
            <div className="rounded bg-neutral-50 px-3 py-2 text-sm">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-neutral-500">Customers will be able to buy</p>
              <ul className="space-y-0.5 text-neutral-800">
                {sizes.map((v) => (
                  <li key={v.variant_id}>
                    {v.variant_name} <span className="text-neutral-400">→</span>{" "}
                    <strong>{packCount(packsAfter(v))}</strong>
                  </li>
                ))}
              </ul>
              {sizes.length > 1 && <p className="mt-1 text-xs text-neutral-500">Stock is shared between these sizes.</p>}
              {afterText && (
                <p className="mt-2 border-t border-neutral-200 pt-2 text-neutral-700">
                  Available after adding: <strong>{afterText}</strong>
                </p>
              )}
            </div>
          )}

          <ExpiryPicker state={expiry} />

          <div>
            <button type="button" onClick={() => setMore((m) => !m)} aria-expanded={more} className="text-sm font-medium text-primary-700 hover:underline">
              {more ? "Hide" : "More options"} {more ? "▾" : "▸"}
            </button>
            {more && (
              <div className="mt-3 space-y-4 rounded border border-neutral-200 p-3">
                <div>
                  <label className={labelCls}>Note</label>
                  <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. delivery reference" className={inputCls} />
                </div>
                {canAssign && sizes.length > 1 && (
                  <div>
                    <label className={labelCls}>Keep some of this for one size only</label>
                    <div className="space-y-1.5">
                      {sizes.map((v) => (
                        <div key={v.variant_id} className="flex items-center gap-2 text-sm">
                          <span className="w-24 text-neutral-700">{v.variant_name}</span>
                          <input
                            type="number"
                            min="0"
                            step="any"
                            value={shares[v.variant_id] ?? ""}
                            onChange={(e) => setShares((cur) => ({ ...cur, [v.variant_id]: e.target.value }))}
                            aria-label={`${v.variant_name} reserved ${unitLabel}`}
                            placeholder="0"
                            className="w-24 rounded border border-neutral-300 px-2 py-1.5 text-right"
                          />
                          <span className="text-xs text-neutral-500">{unitLabel}</span>
                        </div>
                      ))}
                    </div>
                    {overShared && <p className="mt-1 text-xs text-status-danger">That is more than the {plain(amountNum)} {unitLabel} received.</p>}
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </DialogShell>
  );
}

// ---------------------------------------------------------------------------
// Correct stock
// ---------------------------------------------------------------------------

const CORRECT_REASONS = ["Physical count", "Receiving correction", "Data correction", "Other"];

/**
 * CORRECT STOCK: "the system says 50 kg, I counted 43". The difference is
 * shown, never typed - and the server works it out again from the count.
 */
export function CorrectStockDialog({
  product: initial,
  onClose,
  onDone,
}: {
  product: ProductStockItem;
  onClose: () => void;
  onDone: (op: ProductStockOperation) => void;
}) {
  const { getAccessToken } = useAuth();
  const [product, setProduct] = useState(initial);
  const family = stockFamily(product);
  const units = family ? FAMILY_UNITS[family] : [];
  const total = product.totals.find((t) => t.family === family);
  const places = product.warehouses.filter((w) => w.family === family);
  const needsPlace = places.length > 1;

  const [count, setCount] = useState("");
  const [unit, setUnit] = useState(units[0]?.value ?? "KG");
  const [locationId, setLocationId] = useState(needsPlace ? "" : String(places[0]?.location_id ?? ""));
  const [reason, setReason] = useState(CORRECT_REASONS[0]);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const place = places.find((w) => String(w.location_id) === locationId);
  const systemValue = needsPlace ? place?.on_hand_amount : total?.on_hand_amount;
  const systemUnit = (needsPlace ? place?.amount_unit : total?.amount_unit) ?? "kg";
  const baseUnitValue = family ? unitValueForLabel(family, systemUnit) : "KG";
  const systemInUnit = systemValue !== undefined && family ? convertAmount(Number(systemValue), baseUnitValue, unit, family) : null;
  const counted = count !== "" && Number(count) >= 0 ? Number(count) : null;
  const diff = counted !== null && systemInUnit !== null ? counted - systemInUnit : null;
  const unitLabel = units.find((u) => u.value === unit)?.label ?? "";
  const reservedInUnit = !needsPlace && total && family ? convertAmount(Number(total.reserved_amount), baseUnitValue, unit, family) : 0;
  const belowReserved = counted !== null && counted + 0.0005 < reservedInUnit;
  const bigChange = diff !== null && systemInUnit! > 0 && (counted === 0 || Math.abs(diff) / systemInUnit! > 0.25);

  const submit = async () => {
    const token = getAccessToken();
    if (!token || counted === null) return;
    setBusy(true);
    setError(null);
    try {
      const op = await correctProductStock(token, product.product_id, {
        physical_amount: String(counted),
        amount_unit: unit,
        ...(locationId ? { location_id: Number(locationId) } : {}),
        reason,
        ...(notes.trim() ? { notes: notes.trim() } : {}),
      });
      onDone(op);
      onClose();
    } catch (err) {
      const failure = await failureMessage(token, err, "save the correction", product);
      setError(failure.message);
      if (failure.latest) setProduct(failure.latest);
    } finally {
      setBusy(false);
    }
  };

  return (
    <DialogShell
      title={`Correct stock - ${product.product_name}`}
      subtitle="Count what is really there. We work out the difference."
      busy={busy}
      onClose={onClose}
      onSubmit={submit}
      submitLabel="Save correction"
      submitDisabled={counted === null || belowReserved || (needsPlace && !locationId)}
      error={error}
    >
      {needsPlace && (
        <div>
          <label className={labelCls}>Which warehouse did you count?</label>
          <SearchableSelect
            value={locationId}
            onChange={setLocationId}
            placeholder="Choose a warehouse"
            options={places.map((w) => ({ value: String(w.location_id), label: `${w.location_name} - ${plain(w.on_hand_amount)} ${w.amount_unit}` }))}
          />
        </div>
      )}
      <div>
        <p className={labelCls}>System says</p>
        <p className="font-display text-xl font-semibold text-primary-900">
          {systemInUnit === null ? "—" : amountText(Math.round(systemInUnit * 1000) / 1000, unitLabel)}
        </p>
        {!needsPlace && total && Number(total.reserved_amount) > 0 && (
          <p className="text-xs text-neutral-500">{amountText(total.reserved_amount, total.amount_unit)} of this is promised to customer orders.</p>
        )}
      </div>
      <AmountField value={count} onValue={setCount} unit={unit} onUnit={setUnit} family={family} label="Physical count" placeholder="What you counted" autoFocus />
      {diff !== null && (
        <div className="rounded bg-neutral-50 px-3 py-2 text-sm">
          <span className="text-neutral-500">Difference </span>
          <strong className={diff < 0 ? "text-status-danger" : diff > 0 ? "text-primary-800" : "text-neutral-700"}>
            {diff > 0 ? "+" : diff < 0 ? "−" : ""}{plain(Math.abs(Math.round(diff * 1000) / 1000))} {unitLabel}
          </strong>
          {Math.abs(diff) < 0.0005 && <span className="text-neutral-500"> - your count matches, nothing will change.</span>}
        </div>
      )}
      {belowReserved && (
        <p className="text-sm text-status-danger">
          {amountText(plain(reservedInUnit), unitLabel)} is promised to customer orders, so the count can&apos;t be lower than that.
        </p>
      )}
      {bigChange && !belowReserved && <p className="text-sm text-status-warning">This is a big change - check your count first.</p>}
      <div>
        <label className={labelCls}>Reason</label>
        <select value={reason} onChange={(e) => setReason(e.target.value)} className={`${inputCls} bg-white`}>
          {CORRECT_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>
      {reason === "Other" && (
        <div>
          <label className={labelCls}>Note</label>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} className={inputCls} placeholder="What happened?" />
        </div>
      )}
    </DialogShell>
  );
}

// ---------------------------------------------------------------------------
// Remove stock
// ---------------------------------------------------------------------------

export const REMOVE_REASONS = ["Damaged", "Expired", "Spoiled", "Waste", "Customer return", "Other"];

/** REMOVE STOCK: how much and why. Reserved stock is never touched. */
export function RemoveStockAmountDialog({
  product: initial,
  initialReason,
  onClose,
  onDone,
}: {
  product: ProductStockItem;
  initialReason?: string;
  onClose: () => void;
  onDone: (op: ProductStockOperation) => void;
}) {
  const { getAccessToken } = useAuth();
  const [product, setProduct] = useState(initial);
  const family = stockFamily(product);
  const units = family ? FAMILY_UNITS[family] : [];
  const total = product.totals.find((t) => t.family === family);
  const places = product.warehouses.filter((w) => w.family === family && Number(w.amount) > 0);

  const [amount, setAmount] = useState("");
  const [unit, setUnit] = useState(units[0]?.value ?? "KG");
  const [locationId, setLocationId] = useState("");
  const [reason, setReason] = useState(initialReason ?? "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scope = places.find((w) => String(w.location_id) === locationId);
  const availableValue = scope ? scope.amount : total?.amount;
  const availableUnit = (scope ? scope.amount_unit : total?.amount_unit) ?? "kg";
  const baseUnitValue = family ? unitValueForLabel(family, availableUnit) : "KG";
  const availableInUnit = availableValue !== undefined && family ? convertAmount(Number(availableValue), baseUnitValue, unit, family) : 0;
  const unitLabel = units.find((u) => u.value === unit)?.label ?? "";
  const amountNum = Number(amount) > 0 ? Number(amount) : 0;
  const tooMuch = amountNum > availableInUnit + 0.0005;
  const finalReason = reason === "Other" ? (note.trim() ? `Other: ${note.trim()}` : "") : reason;

  const submit = async () => {
    const token = getAccessToken();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const op = await removeProductStock(token, product.product_id, {
        amount: String(amountNum),
        amount_unit: unit,
        ...(locationId ? { location_id: Number(locationId) } : {}),
        reason: finalReason,
      });
      onDone(op);
      onClose();
    } catch (err) {
      const failure = await failureMessage(token, err, "remove stock", product);
      setError(failure.message);
      if (failure.latest) setProduct(failure.latest);
    } finally {
      setBusy(false);
    }
  };

  return (
    <DialogShell
      title={`Remove stock - ${product.product_name}`}
      subtitle={
        <>
          Available: <strong className="text-neutral-800">{amountText(Math.round(availableInUnit * 1000) / 1000, unitLabel)}</strong>
          <span className="block text-xs text-neutral-400">Stock promised to customer orders can&apos;t be removed.</span>
        </>
      }
      busy={busy}
      onClose={onClose}
      onSubmit={submit}
      submitLabel={amountNum > 0 ? `Remove ${plain(amountNum)} ${unitLabel}` : "Remove stock"}
      submitDisabled={!amountNum || tooMuch || !finalReason}
      danger
      error={error}
    >
      <AmountField value={amount} onValue={setAmount} unit={unit} onUnit={setUnit} family={family} label="How much?" autoFocus />
      {tooMuch && <p className="-mt-2 text-sm text-status-danger">Only {amountText(Math.round(availableInUnit * 1000) / 1000, unitLabel)} is available to remove.</p>}
      {places.length > 1 && (
        <div>
          <label className={labelCls}>From</label>
          <select value={locationId} onChange={(e) => setLocationId(e.target.value)} className={`${inputCls} bg-white`}>
            <option value="">Any warehouse (oldest stock first)</option>
            {places.map((w) => <option key={w.location_id} value={w.location_id}>{w.location_name} - {plain(w.amount)} {w.amount_unit}</option>)}
          </select>
        </div>
      )}
      <div>
        <label className={labelCls}>Why?</label>
        <select value={reason} onChange={(e) => setReason(e.target.value)} className={`${inputCls} bg-white`} aria-label="Reason">
          <option value="">Select a reason</option>
          {REMOVE_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>
      {reason === "Other" && (
        <div>
          <label className={labelCls}>What happened?</label>
          <input value={note} onChange={(e) => setNote(e.target.value)} className={inputCls} />
        </div>
      )}
    </DialogShell>
  );
}

// ---------------------------------------------------------------------------
// Move stock
// ---------------------------------------------------------------------------

/** MOVE STOCK: from one warehouse to another, in one action. */
export function MoveStockDialog({
  product: initial,
  onClose,
  onDone,
}: {
  product: ProductStockItem;
  onClose: () => void;
  onDone: (op: ProductStockOperation) => void;
}) {
  const { getAccessToken } = useAuth();
  const [product, setProduct] = useState(initial);
  const { locations } = useWarehouses();
  const family = stockFamily(product);
  const units = family ? FAMILY_UNITS[family] : [];
  const sources = product.warehouses.filter((w) => w.family === family && Number(w.amount) > 0);

  const [fromId, setFromId] = useState(String(sources[0]?.location_id ?? ""));
  const [toId, setToId] = useState("");
  const [amount, setAmount] = useState("");
  const [unit, setUnit] = useState(units[0]?.value ?? "KG");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = sources.find((w) => String(w.location_id) === fromId);
  const to = product.warehouses.find((w) => String(w.location_id) === toId && w.family === family);
  const toName = locations.find((l) => String(l.id) === toId)?.name ?? "";
  const baseUnitValue = family ? unitValueForLabel(family, from?.amount_unit ?? "kg") : "KG";
  const availableInUnit = from && family ? convertAmount(Number(from.amount), baseUnitValue, unit, family) : 0;
  const unitLabel = units.find((u) => u.value === unit)?.label ?? "";
  const amountNum = Number(amount) > 0 ? Number(amount) : 0;
  const tooMuch = amountNum > availableInUnit + 0.0005;
  const round = (n: number) => plain(Math.round(n * 1000) / 1000);
  const toNow = to && family ? convertAmount(Number(to.amount), baseUnitValue, unit, family) : 0;

  const submit = async () => {
    const token = getAccessToken();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const op = await moveProductStock(token, product.product_id, {
        amount: String(amountNum),
        amount_unit: unit,
        from_location_id: Number(fromId),
        to_location_id: Number(toId),
      });
      onDone(op);
      onClose();
    } catch (err) {
      const failure = await failureMessage(token, err, "move stock", product);
      setError(failure.message);
      if (failure.latest) setProduct(failure.latest);
    } finally {
      setBusy(false);
    }
  };

  return (
    <DialogShell
      title={`Move stock - ${product.product_name}`}
      busy={busy}
      onClose={onClose}
      onSubmit={submit}
      submitLabel={amountNum > 0 ? `Move ${plain(amountNum)} ${unitLabel}` : "Move stock"}
      submitDisabled={!amountNum || tooMuch || !fromId || !toId || fromId === toId}
      error={error}
    >
      <div>
        <label className={labelCls}>From</label>
        <select value={fromId} onChange={(e) => setFromId(e.target.value)} className={`${inputCls} bg-white`} aria-label="From warehouse">
          {sources.map((w) => <option key={w.location_id} value={w.location_id}>{w.location_name}</option>)}
        </select>
        {from && <p className="mt-1 text-xs text-neutral-500">{round(availableInUnit)} {unitLabel} available</p>}
      </div>
      <div>
        <label className={labelCls}>To</label>
        <select value={toId} onChange={(e) => setToId(e.target.value)} className={`${inputCls} bg-white`} aria-label="To warehouse">
          <option value="">Choose a warehouse</option>
          {locations.filter((l) => String(l.id) !== fromId).map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
        </select>
      </div>
      <AmountField value={amount} onValue={setAmount} unit={unit} onUnit={setUnit} family={family} label="Amount" autoFocus />
      {tooMuch && <p className="-mt-2 text-sm text-status-danger">Only {round(availableInUnit)} {unitLabel} is available to move.</p>}
      {amountNum > 0 && !tooMuch && from && toId && (
        <div className="rounded bg-neutral-50 px-3 py-2 text-sm">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-neutral-500">After the move</p>
          <p>{from.location_name}: <strong>{round(availableInUnit - amountNum)} {unitLabel}</strong></p>
          <p>{toName}: <strong>{round(toNow + amountNum)} {unitLabel}</strong></p>
        </div>
      )}
    </DialogShell>
  );
}
