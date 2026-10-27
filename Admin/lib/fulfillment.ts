/**
 * Client for the fulfillment state machine in backend fulfillments.py:
 * PENDING -> PICKING -> PACKED -> READY_FOR_DELIVERY -> ASSIGNED ->
 * OUT_FOR_DELIVERY -> DELIVERED. Each call moves exactly one step; the
 * backend decides whether the step is legal and who may take it.
 * Confirming delivery consumes the reserved stock and marks a Cash on
 * Delivery payment as paid.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class FulfillmentApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function post(accessToken: string, path: string, body?: unknown): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/fulfillments${path}`, {
    method: "POST",
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      Authorization: `Bearer ${accessToken}`,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new FulfillmentApiError(response.status, payload?.message ?? "Unable to update this delivery.");
  }
}

export type WarehouseStep = "PICKING" | "PACKED" | "READY_FOR_DELIVERY";

export function advanceFulfillment(accessToken: string, id: number, status: WarehouseStep): Promise<void> {
  return post(accessToken, `/${id}/status`, { status });
}

export function assignDeliveryPartner(accessToken: string, id: number, userId: number): Promise<void> {
  return post(accessToken, `/${id}/assign`, { delivery_partner_user_id: userId });
}

export function markOutForDelivery(accessToken: string, id: number): Promise<void> {
  return post(accessToken, `/${id}/out-for-delivery`);
}

export function confirmDelivery(accessToken: string, id: number, otp: string): Promise<void> {
  return post(accessToken, `/${id}/deliver`, { otp });
}

export interface FulfillmentRow {
  id: number;
  order_id: number;
  status: string;
  delivery_partner_user_id: number | null;
  inventory_location_id: number | null;
  assigned_at: string | null;
  delivered_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FulfillmentList {
  items: FulfillmentRow[];
  page: number;
  page_size: number;
  total: number;
}

export interface FulfillmentOrder {
  fulfillment_id: number;
  order_id: number;
  order_number: string;
  customer_name: string;
  total_amount: string;
  currency: string;
  payment_method: string | null;
  payment_status: string | null;
  items: { id: number; product_name: string; variant_name: string; unit: string; quantity: string }[];
  address: { address_line_1: string; address_line_2: string | null; city: string; state: string; postal_code: string } | null;
}

async function get<T>(accessToken: string, path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/fulfillments${path}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new FulfillmentApiError(response.status, payload?.message ?? "Unable to load deliveries.");
  }
  return response.json() as Promise<T>;
}

export function fetchFulfillments(
  accessToken: string,
  params: { status?: string; page: number; page_size: number },
): Promise<FulfillmentList> {
  const qs = new URLSearchParams({ page: String(params.page), page_size: String(params.page_size) });
  if (params.status) qs.set("status", params.status);
  return get<FulfillmentList>(accessToken, `?${qs.toString()}`);
}

export function fetchFulfillmentOrder(accessToken: string, id: number): Promise<FulfillmentOrder> {
  return get<FulfillmentOrder>(accessToken, `/${id}/order`);
}
