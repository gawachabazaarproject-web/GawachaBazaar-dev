/**
 * Types mirror backend/app/schemas/admin_inventory.py and inventory.py
 * field-for-field. `on_hand`/`reserved`/`available` are always read
 * straight off InventoryLot (available = on_hand - reserved), never
 * recomputed independently here.
 */

import { AMOUNT_UNITS_BY_DIMENSION, UNITS, convert, dimensionOf, formatSize, packTotalText } from "@/lib/units";

export interface AdminInventoryLotListItem {
  id: number;
  product_id: number;
  product_name: string;
  variant_id: number;
  variant_name: string;
  variant_unit: string;
  variant_quantity: string;
  sku: string;
  category_id: number;
  category_name: string;
  location_id: number;
  location_name: string;
  location_code: string;
  batch_id: number;
  batch_code: string;
  batch_expiry_date: string | null;
  on_hand: string;
  reserved: string;
  available: string;
  lot_status: string;
  operational_status: string;
  /** Stock to keep in reserve for this item (null = default) and the value in force. */
  reserve_level: string | null;
  effective_reserve: string | null;
  last_movement_at: string | null;
  updated_at: string;
}

export interface AdminInventoryLotListResponse {
  items: AdminInventoryLotListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface Batch {
  id: number;
  product_id: number;
  product_name: string;
  batch_code: string;
  harvest_date: string;
  expiry_date: string | null;
  quantity: string;
  unit: string;
  status: string;
  supplier_id: number | null;
  supplier_name: string | null;
  wholesaler_user_id: number | null;
  purchase_price: string | null;
  purchase_currency: string | null;
  received_date: string | null;
  receiving_reference: string | null;
  created_at: string;
}

export interface RelatedOrder {
  order_id: number;
  order_number: string;
  reserved_quantity: string;
  reservation_status: string;
}

export interface StockMovement {
  id: number;
  inventory_lot_id: number;
  movement_type: string;
  quantity: string;
  reference_type: string | null;
  reference_id: number | null;
  performed_by_user_id: number;
  occurred_at: string;
  remarks: string | null;
  created_at: string;
}

export interface AdminInventoryLotDetail {
  id: number;
  product_id: number;
  product_name: string;
  product_image_url: string | null;
  category_id: number;
  category_name: string;
  variant_id: number;
  variant_name: string;
  sku: string;
  unit: string;
  variant_quantity: string;
  location_id: number;
  location_name: string;
  location_code: string;
  location_city: string;
  location_status: string;
  batch: Batch;
  on_hand: string;
  reserved: string;
  available: string;
  lot_status: string;
  operational_status: string;
  /** Stock to keep in reserve for this item (null = default) and the value in force. */
  reserve_level: string | null;
  effective_reserve: string | null;
  created_at: string;
  updated_at: string;
  recent_movements: StockMovement[];
  related_orders: RelatedOrder[];
}

export interface InventoryDashboard {
  total_skus: number;
  total_on_hand: string;
  total_reserved: string;
  total_available: string;
  low_stock_count: number;
  out_of_stock_count: number;
  expiring_batches_count: number;
  expired_batches_count: number;
  recent_movements: StockMovement[];
  warehouses_requiring_attention: number;
}

export interface Location {
  id: number;
  name: string;
  code: string;
  type: string;
  city: string;
  status: string;
  address_line_1?: string;
  latitude?: number | null;
  longitude?: number | null;
  /** Delivery distance is measured from this location. */
  is_packing_point?: boolean;
}

export const OPERATIONAL_STATUSES = ["IN_STOCK", "LOW_STOCK", "OUT_OF_STOCK", "EXPIRING", "EXPIRED", "INACTIVE"] as const;
export const ADJUSTMENT_REASONS = [
  "Receiving correction",
  "Physical count",
  "Damaged stock correction",
  "Wastage",
  "Expiry",
  "Theft/loss",
  "Data correction",
  "Other",
] as const;

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class InventoryApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(accessToken: string, path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      Authorization: `Bearer ${accessToken}`,
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new InventoryApiError(response.status, body?.message ?? "Something went wrong.");
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export interface AdminLotListParams {
  page?: number;
  page_size?: number;
  location_id?: number;
  category_id?: number;
  status?: string;
  operational_status?: string;
  batch_id?: number;
  q?: string;
}

export async function fetchDashboard(accessToken: string): Promise<InventoryDashboard> {
  return request(accessToken, "/inventory/admin/dashboard");
}

export async function fetchAdminLots(
  accessToken: string,
  params: AdminLotListParams,
): Promise<AdminInventoryLotListResponse> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  return request(accessToken, `/inventory/admin/lots?${search.toString()}`);
}

export interface ProductStockVariant {
  variant_id: number;
  variant_name: string;
  sku: string;
  status: string;
  pack_quantity: string;
  pack_unit: string;
  /** Whole packs this size can sell: its own share plus the unassigned stock. */
  available_packs: string;
  /** What those packs add up to, in `amount_unit` (kg / L / pcs). */
  available_amount: string;
  amount_unit: string;
  /** Stock assigned to this size alone (in `amount_unit`) and the packs it makes. */
  share_amount: string;
  share_packs: string;
}

export interface ProductStockTotal {
  family: string;
  /** Available to sell: what is there minus what is promised to orders. */
  amount: string;
  amount_unit: string;
  unassigned_amount: string;
  /** Everything physically there (including the reserved part). */
  on_hand_amount: string;
  /** Promised to customer orders. */
  reserved_amount: string;
  /** The product-level low-stock reserve in `amount_unit` (null = the per-size levels apply). */
  reserve_amount?: string | null;
}

export interface ProductWarehouseStock {
  location_id: number;
  location_name: string;
  family: string;
  /** Available to sell here. */
  amount: string;
  amount_unit: string;
  /** Everything physically here (reserved included). */
  on_hand_amount: string;
}

export interface ProductExpiry {
  expiry_date: string;
  /** Negative once it has expired. */
  days_left: number;
  amount: string;
  amount_unit: string;
}

export type StockStatus = "OK" | "LOW" | "OUT";

export interface ProductStockItem {
  product_id: number;
  product_name: string;
  category_name: string;
  /** Stock per unit family, e.g. "34 kg" of which "10 kg" is still unassigned. */
  totals: ProductStockTotal[];
  variants: ProductStockVariant[];
  stock_status: StockStatus;
  /** Draft / hidden products never show as low or out: they cannot be bought. */
  product_status: string;
  warehouses: ProductWarehouseStock[];
  expiry: ProductExpiry | null;
}

export interface ProductStockSummary {
  all: number;
  low: number;
  out: number;
  expiring: number;
}

export type StockFilter = "all" | "low" | "out" | "expiring";

export interface StockChange {
  lot_id: number;
  location_id: number;
  location_name: string;
  variant_id: number;
  movement_type: string;
  packs: string;
}

export interface ProductStockOperation {
  operation_id: number | null;
  kind: "correct" | "remove" | "move" | "undo";
  message: string;
  difference: string;
  amount_unit: string;
  changes: StockChange[];
  undo_until: string | null;
  product: ProductStockItem;
}

export interface ProductStockListResponse {
  items: ProductStockItem[];
  page: number;
  page_size: number;
  total: number;
}

export async function fetchProductStock(
  accessToken: string,
  params: { page?: number; page_size?: number; category_id?: number; q?: string; status?: StockFilter },
): Promise<ProductStockListResponse> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  return request(accessToken, `/inventory/admin/products?${search.toString()}`);
}

export async function fetchProductStockSummary(
  accessToken: string,
  params: { category_id?: number; q?: string },
): Promise<ProductStockSummary> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  return request(accessToken, `/inventory/admin/products/summary?${search.toString()}`);
}

/** "I counted 43 kg": the server works out the difference and picks the lots. */
export async function setProductReserve(
  accessToken: string,
  productId: number,
  payload: { amount: string; amount_unit: string },
): Promise<ProductStockItem> {
  return request(accessToken, `/inventory/admin/products/${productId}/reserve`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function clearProductReserve(accessToken: string, productId: number): Promise<ProductStockItem> {
  return request(accessToken, `/inventory/admin/products/${productId}/reserve`, { method: "DELETE" });
}

export async function correctProductStock(
  accessToken: string,
  productId: number,
  payload: { physical_amount: string; amount_unit: string; location_id?: number; reason: string; notes?: string },
): Promise<ProductStockOperation> {
  return request(accessToken, `/inventory/admin/products/${productId}/correct`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function removeProductStock(
  accessToken: string,
  productId: number,
  payload: { amount: string; amount_unit: string; location_id?: number; reason: string },
): Promise<ProductStockOperation> {
  return request(accessToken, `/inventory/admin/products/${productId}/remove`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function moveProductStock(
  accessToken: string,
  productId: number,
  payload: { amount: string; amount_unit: string; from_location_id: number; to_location_id: number },
): Promise<ProductStockOperation> {
  return request(accessToken, `/inventory/admin/products/${productId}/move`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Reverses a recent correct / remove / move (the server refuses when unsafe). */
export async function undoStockAction(accessToken: string, operationId: number): Promise<ProductStockOperation> {
  return request(accessToken, `/inventory/admin/stock-actions/${operationId}/undo`, { method: "POST" });
}

/** Sets how much stock each listed size has been assigned (its whole share). */
export async function setStockShares(
  accessToken: string,
  productId: number,
  shares: { variant_id: number; amount: string; amount_unit: string }[],
  /** true: the amounts are added to each size's current share instead of replacing it. */
  add = false,
): Promise<ProductStockItem> {
  return request(accessToken, `/inventory/admin/products/${productId}/stock-shares`, {
    method: "PUT",
    body: JSON.stringify({ shares, add }),
  });
}

export async function fetchLotDetail(accessToken: string, id: number): Promise<AdminInventoryLotDetail> {
  return request(accessToken, `/inventory/admin/lots/${id}`);
}

export async function fetchLocations(accessToken: string): Promise<Location[]> {
  const result = await request<{ items: Location[] }>(accessToken, "/inventory/locations?page_size=100");
  return result.items;
}

export interface CreateLocationPayload {
  name: string;
  code: string;
  type: string;
  address_line_1: string;
  address_line_2?: string | null;
  city: string;
  state: string;
  postal_code: string;
  latitude?: number | null;
  longitude?: number | null;
}

export async function updateLocationCoordinates(
  accessToken: string,
  id: number,
  latitude: number | null,
  longitude: number | null,
): Promise<Location> {
  return request(accessToken, `/inventory/locations/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ latitude, longitude }),
  });
}

export async function deleteLocation(accessToken: string, id: number): Promise<void> {
  await request(accessToken, `/inventory/locations/${id}`, { method: "DELETE" });
}

export async function setPackingPoint(accessToken: string, id: number): Promise<Location> {
  return request(accessToken, `/inventory/locations/${id}/packing-point`, { method: "POST" });
}

export async function createLocation(accessToken: string, payload: CreateLocationPayload): Promise<Location> {
  return request(accessToken, "/inventory/locations", { method: "POST", body: JSON.stringify(payload) });
}

export async function fetchBatches(accessToken: string, productId?: number): Promise<Batch[]> {
  const search = new URLSearchParams({ page_size: "100" });
  if (productId) search.set("product_id", String(productId));
  const result = await request<{ items: Batch[] }>(accessToken, `/inventory/batches?${search.toString()}`);
  return result.items;
}

export interface CreateBatchPayload {
  product_id: number;
  batch_code: string;
  harvest_date: string;
  expiry_date?: string | null;
  quantity: string;
  unit: string;
  status: string;
  supplier_id?: number | null;
  received_date?: string | null;
}

export async function createBatch(accessToken: string, payload: CreateBatchPayload): Promise<Batch> {
  return request(accessToken, "/inventory/batches", { method: "POST", body: JSON.stringify(payload) });
}

export async function receiveStock(
  accessToken: string,
  payload: {
    batch_id?: number;
    variant_id: number;
    location_id: number;
    quantity?: string;
    amount?: string;
    amount_unit?: string;
    remarks?: string;
    /** Date the delivery should be used by (new delivery only). */
    expiry_date?: string;
  },
): Promise<AdminInventoryLotListItem> {
  return request(accessToken, "/inventory/admin/receive", { method: "POST", body: JSON.stringify(payload) });
}

export async function reconcileStock(
  accessToken: string,
  lotId: number,
  payload: { physical_count: string; reason: string; notes?: string },
): Promise<AdminInventoryLotListItem> {
  return request(accessToken, `/inventory/admin/lots/${lotId}/reconcile`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function adjustStock(
  accessToken: string,
  lotId: number,
  payload: { movement_type: string; quantity?: string; amount?: string; amount_unit?: string; remarks: string },
): Promise<StockMovement> {
  return request(accessToken, `/inventory/lots/${lotId}/movements`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function transferStock(
  accessToken: string,
  payload: { source_lot_id: number; destination_location_id: number; quantity: string; remarks?: string },
): Promise<{ source_lot: AdminInventoryLotListItem; destination_lot: AdminInventoryLotListItem }> {
  return request(accessToken, "/inventory/admin/transfer", { method: "POST", body: JSON.stringify(payload) });
}


/** Take stock out of a lot. Omit `quantity` to remove everything available. */
export async function removeStock(
  accessToken: string,
  lotId: number,
  payload: { quantity?: string; reason: string },
): Promise<AdminInventoryLotListItem> {
  return request(accessToken, `/inventory/admin/lots/${lotId}/remove`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface StockAlertItem {
  product_id: number;
  variant_id: number;
  product_name: string;
  variant_name: string;
  unit: string;
  pack_quantity: string;
  available: string;
  reserve_level: string;
  level: "OUT" | "BELOW" | "NEAR";
}

export interface StockAlerts {
  count: number;
  out_count: number;
  below_count: number;
  near_count: number;
  /** Products (not sizes) that are out of stock / running low. */
  products_out: number;
  products_low: number;
  items: StockAlertItem[];
}

/** Items out of stock, at/below their reserve level, or close to it. */
export async function fetchStockAlerts(accessToken: string, limit?: number): Promise<StockAlerts> {
  return request(accessToken, `/inventory/admin/stock-alerts${limit ? `?limit=${limit}` : ""}`);
}

function trim(n: number): string {
  return String(Number(n.toFixed(3)));
}

/** Stock is counted in packs of the variant ("100 packs"), not in the
 * pack's own unit - this is the count label. */
export function packCount(packs: string | number): string {
  const n = Number(packs);
  return `${trim(n)} ${n === 1 ? "pack" : "packs"}`;
}

/** What a number of packs adds up to in real units ("100 kg"), or null
 * when the pack has no meaningful total (a pack counted as "1 pack"). */
export function packTotal(packs: string | number, packQuantity: string | number, unit: string): string | null {
  return packTotalText(packs, packQuantity, unit);
}

/** Units stock can be entered in for a pack unit - weight/volume first (kg for
 * KG/G packs), or none when the pack can only be counted ("5 packs"). */
export function amountUnits(unit: string): { value: string; label: string }[] {
  const dimension = dimensionOf(unit);
  return (dimension ? AMOUNT_UNITS_BY_DIMENSION[dimension] ?? [] : []).map((value) => ({
    value,
    label: UNITS[value].inputLabel,
  }));
}

/** Preview of how many packs an entered weight makes (the server does the real conversion). */
export function amountToPacks(amount: string | number, amountUnit: string, packQuantity: string | number, unit: string): number {
  if (!UNITS[amountUnit] || !UNITS[unit]) return 0;
  const packs = (Number(amount) * UNITS[amountUnit].factor) / (Number(packQuantity) * UNITS[unit].factor);
  return Math.floor(packs * 1000) / 1000;
}

/** "1 kg" - the size of one pack. */
export function packSize(packQuantity: string | number, unit: string): string {
  return formatSize(packQuantity, unit);
}

// ---- Units staff talk in (kg / L / pieces), per unit family ----------------

export const FAMILY_UNITS: Record<string, { value: string; label: string; factor: number }[]> = Object.fromEntries(
  Object.entries(AMOUNT_UNITS_BY_DIMENSION).map(([dimension, values]) => [
    dimension,
    values.map((value) => ({ value, label: UNITS[value].inputLabel, factor: UNITS[value].factor })),
  ]),
);

/** Plain number without trailing zeros ("50", "2.5"). */
export function plain(value: string | number): string {
  return String(Number(Number(value).toFixed(3)));
}

/** "50 kg" - the way a stock figure is read out. */
export function amountText(amount: string | number, unit: string): string {
  return `${plain(amount)} ${unit}`;
}

/** Convert between the units of one family ("2" kg -> 2000 g). */
export function convertAmount(amount: number, fromUnit: string, toUnit: string, family: string): number {
  void family; // kept for callers; the dimension now comes from the units themselves
  return convert(amount, fromUnit, toUnit) ?? amount;
}

/** What the server will say went wrong, in words for staff. Never "something went wrong". */
export function stockErrorMessage(err: unknown, action: string, unchanged = "Your stock was not changed."): string {
  if (err instanceof InventoryApiError) {
    if (err.status === 401 || err.status === 403) return `You don't have permission to ${action}.`;
    if (err.status >= 500) return `Couldn't ${action} - the server had a problem. ${unchanged}`;
    return `Couldn't ${action}. ${err.message} ${unchanged}`;
  }
  return `Couldn't ${action} - the connection failed. ${unchanged}`;
}

/** One product's current stock - read right before a stock action so nobody works from a stale number. */
export async function fetchProductStockCard(accessToken: string, productId: number): Promise<ProductStockItem> {
  return request(accessToken, `/inventory/admin/products/${productId}`);
}

/** "Expires today / tomorrow / in 3 days", "Expired yesterday" - never a raw date or day count. */
export function expiryPhrase(daysLeft: number): string {
  if (daysLeft < -1) return `Expired ${-daysLeft} days ago`;
  if (daysLeft === -1) return "Expired yesterday";
  if (daysLeft === 0) return "Expires today";
  if (daysLeft === 1) return "Expires tomorrow";
  return `Expires in ${daysLeft} days`;
}

/** The unit option ("KG") for a displayed unit label ("kg", "pcs") within a family. */
export function unitValueForLabel(family: string, label: string): string {
  const units = FAMILY_UNITS[family] ?? [];
  return units.find((u) => u.label === label || (label === "pcs" && u.value === "UNIT"))?.value ?? units[0]?.value ?? "";
}
