/**
 * Types mirror backend/app/schemas/promotion.py field-for-field. Decimal/
 * money fields are strings (FastAPI serializes Pydantic Decimal as a JSON
 * string) - parse only for display, never for further math. Every
 * eligibility/discount number shown anywhere in this module comes straight
 * from the backend's PromotionService - nothing here recomputes a discount.
 */

export const DISCOUNT_TYPES = ["PERCENTAGE", "FIXED_AMOUNT"] as const;
export const CUSTOMER_SCOPES = ["ALL", "NEW_CUSTOMERS", "EXISTING_CUSTOMERS", "SPECIFIC"] as const;
export const PROMOTION_ADMIN_STATUSES = ["DRAFT", "ACTIVE", "PAUSED", "DISABLED"] as const;
export const PROMOTION_EFFECTIVE_STATUSES = ["DRAFT", "SCHEDULED", "ACTIVE", "PAUSED", "EXPIRED", "DISABLED"] as const;

export interface PromotionTarget {
  target_type: "PRODUCT" | "CATEGORY";
  target_id: number;
  target_name: string | null;
}

export interface PromotionListItem {
  id: number;
  name: string;
  discount_type: string;
  discount_value: string;
  code: string | null;
  customer_scope: string;
  admin_status: string;
  effective_status: string;
  priority: number;
  usage_limit_total: number | null;
  redemption_count: number;
  starts_at: string;
  ends_at: string | null;
  created_by_name: string;
  created_at: string;
  updated_at: string;
}

export interface PromotionListResponse {
  items: PromotionListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface PromotionPerformance {
  redemption_count: number;
  reversed_count: number;
  total_discount_granted: string;
  revenue_influenced: string;
  average_order_value: string | null;
}

export interface PromotionDetail {
  id: number;
  name: string;
  description: string | null;
  customer_title: string | null;
  customer_description: string | null;
  code: string | null;
  discount_type: string;
  discount_value: string;
  max_discount_amount: string | null;
  min_order_value: string | null;
  min_quantity: string | null;
  customer_scope: string;
  eligible_customer_ids: number[];
  admin_status: string;
  effective_status: string;
  stacking_policy: string;
  priority: number;
  usage_limit_total: number | null;
  usage_limit_per_customer: number | null;
  redemption_count: number;
  starts_at: string;
  ends_at: string | null;
  targets: PromotionTarget[];
  created_by_name: string;
  created_at: string;
  updated_at: string;
  performance: PromotionPerformance;
}

export interface PromotionRedemptionRow {
  id: number;
  order_id: number;
  order_number: string;
  order_status: string;
  customer_id: number;
  customer_name: string;
  discount_amount: string;
  order_total: string;
  status: string;
  redeemed_at: string;
}

export interface PromotionRedemptionListResponse {
  items: PromotionRedemptionRow[];
  page: number;
  page_size: number;
  total: number;
}

export interface PromotionsDashboard {
  active_count: number;
  scheduled_count: number;
  expired_count: number;
  draft_count: number;
  disabled_count: number;
  paused_count: number;
  total_redemptions: number;
  total_discount_granted: string;
  ending_soon: PromotionListItem[];
  most_used: PromotionListItem[];
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class PromotionApiError extends Error {
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
    throw new PromotionApiError(response.status, body?.message ?? "Something went wrong.");
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export async function fetchPromotionsDashboard(accessToken: string): Promise<PromotionsDashboard> {
  return request(accessToken, "/promotions/dashboard");
}

export interface PromotionListParams {
  page?: number;
  page_size?: number;
  admin_status?: string;
  effective_status?: string;
  q?: string;
}

export async function fetchPromotions(
  accessToken: string,
  params: PromotionListParams,
): Promise<PromotionListResponse> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  return request(accessToken, `/promotions?${search.toString()}`);
}

export async function fetchPromotionDetail(accessToken: string, id: number): Promise<PromotionDetail> {
  return request(accessToken, `/promotions/${id}`);
}

export async function fetchPromotionRedemptions(
  accessToken: string,
  id: number,
  page: number = 1,
  pageSize: number = 20,
): Promise<PromotionRedemptionListResponse> {
  return request(accessToken, `/promotions/${id}/redemptions?page=${page}&page_size=${pageSize}`);
}

export interface PromotionTargetInput {
  target_type: "PRODUCT" | "CATEGORY";
  target_id: number;
}

export interface CreatePromotionPayload {
  name: string;
  description?: string | null;
  customer_title?: string | null;
  customer_description?: string | null;
  code?: string | null;
  discount_type: string;
  discount_value: number;
  max_discount_amount?: number | null;
  min_order_value?: number | null;
  min_quantity?: number | null;
  customer_scope: string;
  eligible_customer_ids?: number[];
  status: string;
  priority?: number;
  usage_limit_total?: number | null;
  usage_limit_per_customer?: number | null;
  starts_at: string;
  ends_at?: string | null;
  targets?: PromotionTargetInput[];
}

export async function createPromotion(accessToken: string, payload: CreatePromotionPayload): Promise<PromotionDetail> {
  return request(accessToken, "/promotions", { method: "POST", body: JSON.stringify(payload) });
}

export type UpdatePromotionPayload = Partial<CreatePromotionPayload>;

export async function updatePromotion(
  accessToken: string,
  id: number,
  payload: UpdatePromotionPayload,
): Promise<PromotionDetail> {
  return request(accessToken, `/promotions/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export async function duplicatePromotion(accessToken: string, id: number): Promise<PromotionDetail> {
  return request(accessToken, `/promotions/${id}/duplicate`, { method: "POST" });
}

export async function activatePromotion(accessToken: string, id: number): Promise<PromotionDetail> {
  return request(accessToken, `/promotions/${id}/activate`, { method: "POST" });
}

export async function pausePromotion(accessToken: string, id: number): Promise<PromotionDetail> {
  return request(accessToken, `/promotions/${id}/pause`, { method: "POST" });
}

export async function disablePromotion(accessToken: string, id: number): Promise<PromotionDetail> {
  return request(accessToken, `/promotions/${id}/disable`, { method: "POST" });
}
