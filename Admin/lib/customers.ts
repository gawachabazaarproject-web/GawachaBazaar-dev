/**
 * Types mirror backend/app/schemas/admin_customer.py field-for-field. A
 * "customer" is not a separate table - it is an existing User holding the
 * CUSTOMER role (see backend/app/core/roles.py). Order rows reuse the exact
 * AdminOrderListItemResponse shape from the Orders module (see
 * CustomerOrderListItem below) - this module never redescribes an order.
 */

export const CUSTOMER_ACCOUNT_STATUSES = ["ACTIVE", "INACTIVE", "SUSPENDED"] as const;
export const CUSTOMER_ACTIVITY_FILTERS = [
  "new",
  "returning",
  "no_orders",
  "recently_active",
  "inactive",
] as const;

export interface CustomersDashboard {
  total_customers: number;
  active_customers: number;
  inactive_customers: number;
  suspended_customers: number;
  new_customers_last_30_days: number;
  customers_with_orders: number;
  customers_with_no_orders: number;
  returning_customers: number;
  average_order_value: string | null;
  total_realized_revenue: string;
}

export interface AdminCustomerListItem {
  id: number;
  name: string;
  email: string;
  phone: string;
  account_status: string;
  order_count: number;
  completed_order_count: number;
  total_spend: string;
  average_order_value: string | null;
  last_order_at: string | null;
  created_at: string;
}

export interface AdminCustomerListResponse {
  items: AdminCustomerListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface CustomerOrderSummary {
  total_orders: number;
  completed_orders: number;
  cancelled_orders: number;
  pending_orders: number;
  total_spend: string;
  average_order_value: string | null;
  first_order_at: string | null;
  last_order_at: string | null;
  promotion_redemptions_count: number;
}

export interface CustomerAddress {
  id: number;
  label: string;
  address_line_1: string;
  address_line_2: string | null;
  city: string;
  state: string;
  postal_code: string;
  latitude: string | null;
  longitude: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface PendingContactChange {
  field: string;
  new_value: string;
  expires_at: string;
  attempts: number;
}

export interface AdminCustomerDetail {
  id: number;
  name: string;
  email: string;
  phone: string;
  account_status: string;
  roles: string[];
  is_bulk_customer: boolean;
  created_at: string;
  updated_at: string;
  summary: CustomerOrderSummary;
  addresses: CustomerAddress[];
  pending_email_change: PendingContactChange | null;
  pending_phone_change: PendingContactChange | null;
}

// Reuses the exact Orders-module row shape (backend/app/schemas/admin_order.py)
export interface CustomerOrderListItem {
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

export interface CustomerOrderListResponse {
  items: CustomerOrderListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface CustomerPromotionRedemptionRow {
  id: number;
  promotion_id: number;
  promotion_name: string;
  promotion_code: string | null;
  order_id: number;
  order_number: string;
  discount_amount: string;
  status: string;
  redeemed_at: string;
}

export interface CustomerPromotionRedemptionListResponse {
  items: CustomerPromotionRedemptionRow[];
  page: number;
  page_size: number;
  total: number;
}

export interface CustomerTimelineEvent {
  event_type: string;
  occurred_at: string;
  title: string;
  description: string | null;
  resource_type: string | null;
  resource_id: number | null;
}

export interface CustomerNote {
  id: number;
  user_id: number;
  note: string;
  author_name: string;
  created_at: string;
  updated_at: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class CustomerApiError extends Error {
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
    throw new CustomerApiError(response.status, body?.message ?? "Something went wrong.");
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export async function fetchCustomersDashboard(accessToken: string): Promise<CustomersDashboard> {
  return request(accessToken, "/customers/dashboard");
}

export interface CustomerListParams {
  page?: number;
  page_size?: number;
  q?: string;
  account_status?: string;
  activity?: string;
  has_orders?: boolean;
  registered_from?: string;
  registered_to?: string;
  last_order_from?: string;
  last_order_to?: string;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}

export async function fetchCustomers(
  accessToken: string,
  params: CustomerListParams,
): Promise<AdminCustomerListResponse> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  return request(accessToken, `/customers?${search.toString()}`);
}

export async function fetchCustomerDetail(accessToken: string, id: number): Promise<AdminCustomerDetail> {
  return request(accessToken, `/customers/${id}`);
}

export async function fetchCustomerOrders(
  accessToken: string,
  id: number,
  page: number = 1,
  pageSize: number = 20,
): Promise<CustomerOrderListResponse> {
  return request(accessToken, `/customers/${id}/orders?page=${page}&page_size=${pageSize}`);
}

export async function fetchCustomerPromotions(
  accessToken: string,
  id: number,
  page: number = 1,
  pageSize: number = 20,
): Promise<CustomerPromotionRedemptionListResponse> {
  return request(accessToken, `/customers/${id}/promotions?page=${page}&page_size=${pageSize}`);
}

export async function fetchCustomerAddresses(accessToken: string, id: number): Promise<CustomerAddress[]> {
  return request(accessToken, `/customers/${id}/addresses`);
}

export async function fetchCustomerTimeline(accessToken: string, id: number): Promise<CustomerTimelineEvent[]> {
  const result = await request<{ items: CustomerTimelineEvent[] }>(accessToken, `/customers/${id}/timeline`);
  return result.items;
}

export async function fetchCustomerNotes(accessToken: string, id: number): Promise<CustomerNote[]> {
  const result = await request<{ items: CustomerNote[] }>(accessToken, `/customers/${id}/notes`);
  return result.items;
}

export async function createCustomerNote(accessToken: string, id: number, note: string): Promise<CustomerNote> {
  return request(accessToken, `/customers/${id}/notes`, { method: "POST", body: JSON.stringify({ note }) });
}

export async function updateCustomerNote(
  accessToken: string,
  noteId: number,
  note: string,
): Promise<CustomerNote> {
  return request(accessToken, `/customers/notes/${noteId}`, { method: "PATCH", body: JSON.stringify({ note }) });
}

export async function setCustomerStatus(
  accessToken: string,
  id: number,
  status: string,
  reason?: string,
): Promise<AdminCustomerDetail> {
  return request(accessToken, `/customers/${id}/status`, {
    method: "POST",
    body: JSON.stringify({ status, reason: reason || undefined }),
  });
}

export async function requestContactChange(
  accessToken: string,
  id: number,
  field: "EMAIL" | "PHONE",
  newValue: string,
): Promise<PendingContactChange> {
  return request(accessToken, `/customers/${id}/contact-change`, {
    method: "POST",
    body: JSON.stringify({ field, new_value: newValue }),
  });
}

export async function confirmContactChange(
  accessToken: string,
  id: number,
  field: "EMAIL" | "PHONE",
  code: string,
): Promise<AdminCustomerDetail> {
  return request(accessToken, `/customers/${id}/contact-change/confirm`, {
    method: "POST",
    body: JSON.stringify({ field, code }),
  });
}

export async function cancelContactChange(
  accessToken: string,
  id: number,
  field: "EMAIL" | "PHONE",
): Promise<void> {
  await request(accessToken, `/customers/${id}/contact-change/${field}`, { method: "DELETE" });
}
