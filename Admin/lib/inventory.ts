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

export async function fetchLotDetail(accessToken: string, id: number): Promise<AdminInventoryLotDetail> {
  return request(accessToken, `/inventory/admin/lots/${id}`);
}

export async function fetchLocations(accessToken: string): Promise<Location[]> {
  const result = await request<{ items: Location[] }>(accessToken, "/inventory/locations?page_size=100");
  return result.items;
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
  payload: { batch_id: number; variant_id: number; location_id: number; quantity: string; remarks?: string },
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
  payload: { movement_type: string; quantity: string; remarks: string },
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
