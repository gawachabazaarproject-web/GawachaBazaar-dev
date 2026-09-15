/**
 * Types mirror backend/app/schemas/admin_order.py field-for-field. Every
 * money/quantity value is a string here because FastAPI serializes
 * Pydantic Decimal fields as JSON strings, not numbers - parse with
 * Number(...) only for display formatting, never for further math (the
 * backend is the only place a financial total is computed).
 */

export interface AdminOrderListItem {
  id: number;
  order_number: string;
  status: string;
  total_amount: string;
  discount_amount: string;
  applied_promo_code: string | null;
  currency: string;
  placed_at: string;
  customer_id: number;
  customer_name: string;
  customer_email: string;
  item_count: number;
  payment_status: string | null;
  payment_method: string | null;
  fulfillment_status: string | null;
  delivery_partner_user_id: number | null;
}

export interface AdminOrderListResponse {
  items: AdminOrderListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface OrderItemLine {
  id: number;
  variant_id: number;
  product_name: string;
  variant_name: string;
  sku: string;
  unit: string;
  quantity: string;
  unit_price: string;
  total_price: string;
}

export interface OrderAddress {
  address_line_1: string;
  address_line_2: string | null;
  city: string;
  state: string;
  postal_code: string;
  latitude: string | null;
  longitude: string | null;
}

export interface PaymentInfo {
  id: number;
  order_id: number;
  payment_method: string;
  status: string;
  amount: string;
  currency: string;
  gateway_name: string | null;
  gateway_order_id: string | null;
  paid_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FulfillmentInfo {
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

export interface RefundInfo {
  id: number;
  order_id: number;
  status: string;
  amount: string;
  currency: string;
  requested_at: string;
  created_at: string;
  updated_at: string;
  payment_id: number;
  approved_by_user_id: number | null;
  approved_at: string | null;
  rejection_reason: string | null;
  processed_at: string | null;
}

export interface AdminOrderDetail {
  id: number;
  order_number: string;
  status: string;
  subtotal_amount: string;
  discount_amount: string;
  total_amount: string;
  applied_promo_code: string | null;
  currency: string;
  placed_at: string;
  created_at: string;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  cancelled_by_user_id: number | null;
  items: OrderItemLine[];
  address: OrderAddress | null;
  customer_id: number;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  payment: PaymentInfo | null;
  fulfillment: FulfillmentInfo | null;
  refund: RefundInfo | null;
}

export interface AdminOrderListParams {
  page?: number;
  page_size?: number;
  status?: string;
  payment_status?: string;
  fulfillment_status?: string;
  date_from?: string;
  date_to?: string;
  q?: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class OrdersApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function get<T>(accessToken: string, path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new OrdersApiError(response.status, body?.message ?? "Unable to load orders.");
  }
  return response.json();
}

export async function fetchAdminOrders(
  accessToken: string,
  params: AdminOrderListParams,
): Promise<AdminOrderListResponse> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  return get(accessToken, `/orders/admin?${search.toString()}`);
}

export async function fetchAdminOrderDetail(accessToken: string, orderId: number): Promise<AdminOrderDetail> {
  return get(accessToken, `/orders/admin/${orderId}`);
}

export async function cancelAdminOrder(
  accessToken: string,
  orderId: number,
  reason: string,
): Promise<AdminOrderDetail> {
  const response = await fetch(`${API_BASE_URL}/orders/admin/${orderId}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ reason: reason || null }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new OrdersApiError(response.status, body?.message ?? "Unable to cancel this order.");
  }
  return response.json();
}

/** Order statuses that may still legally be cancelled - mirrors
 * order_state.py's TERMINAL_ORDER_STATUSES (the inverse of it). This is
 * UI-only convenience for hiding a button that would just get rejected;
 * the backend re-validates the transition regardless (see order_state.py -
 * "the admin frontend must never decide whether a state transition is
 * valid"). */
export function isOrderCancellable(status: string): boolean {
  return status === "PENDING" || status === "CONFIRMED";
}
