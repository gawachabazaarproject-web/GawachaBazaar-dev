/**
 * Types mirror backend/app/schemas/admin_inventory.py and inventory.py
 * field-for-field. `on_hand`/`reserved`/`available` are always read
 * straight off InventoryLot (available = on_hand - reserved), never
 * recomputed independently here.
 */

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

export interface ProductStockItem {
  product_id: number;
  product_name: string;
  category_name: string;
  /** Stock per unit family, e.g. "34 kg" of which "10 kg" is still unassigned. */
  totals: { family: string; amount: string; amount_unit: string; unassigned_amount: string }[];
  variants: ProductStockVariant[];
}

export interface ProductStockListResponse {
  items: ProductStockItem[];
  page: number;
  page_size: number;
  total: number;
}

export async function fetchProductStock(
  accessToken: string,
  params: { page?: number; page_size?: number; category_id?: number; q?: string },
): Promise<ProductStockListResponse> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  return request(accessToken, `/inventory/admin/products?${search.toString()}`);
}

/** Sets how much stock each listed size has been assigned (its whole share). */
export async function setStockShares(
  accessToken: string,
  productId: number,
  shares: { variant_id: number; amount: string; amount_unit: string }[],
): Promise<ProductStockItem> {
  return request(accessToken, `/inventory/admin/products/${productId}/stock-shares`, {
    method: "PUT",
    body: JSON.stringify({ shares }),
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
  available: string;
  reserve_level: string;
  level: "OUT" | "BELOW" | "NEAR";
}

export interface StockAlerts {
  count: number;
  out_count: number;
  below_count: number;
  near_count: number;
  items: StockAlertItem[];
}

/** Items out of stock, at/below their reserve level, or close to it. */
export async function fetchStockAlerts(accessToken: string): Promise<StockAlerts> {
  return request(accessToken, "/inventory/admin/stock-alerts");
}

const UNIT_BASE: Record<string, [number, string, number, string]> = {
  // unit -> [base factor, base label, factor of the larger display unit, its label]
  KG: [1000, "g", 1000, "kg"],
  G: [1, "g", 1000, "kg"],
  L: [1000, "ml", 1000, "L"],
  ML: [1, "ml", 1000, "L"],
};

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
  const total = Number(packs) * Number(packQuantity);
  const conv = UNIT_BASE[unit];
  if (!conv) return `${trim(total)} ${unit.toLowerCase()}`;
  const base = total * conv[0];
  return base >= conv[2] ? `${trim(base / conv[2])} ${conv[3]}` : `${trim(base)} ${conv[1]}`;
}

/** Units stock can be entered in for a pack unit - weight/volume first (kg for
 * KG/G packs), or none when the pack can only be counted ("5 packs"). */
export function amountUnits(unit: string): { value: string; label: string }[] {
  if (unit === "KG" || unit === "G") return [{ value: "KG", label: "kg" }, { value: "G", label: "g" }];
  if (unit === "L" || unit === "ML") return [{ value: "L", label: "L" }, { value: "ML", label: "ml" }];
  return [];
}

/** Preview of how many packs an entered weight makes (the server does the real conversion). */
export function amountToPacks(amount: string | number, amountUnit: string, packQuantity: string | number, unit: string): number {
  const base = (u: string) => (u === "KG" || u === "L" ? 1000 : 1);
  const packs = (Number(amount) * base(amountUnit)) / (Number(packQuantity) * base(unit));
  return Math.floor(packs * 1000) / 1000;
}

/** "1 kg" - the size of one pack. */
export function packSize(packQuantity: string | number, unit: string): string {
  return `${trim(Number(packQuantity))} ${unit.toLowerCase()}`;
}
