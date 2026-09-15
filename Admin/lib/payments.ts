/**
 * Types mirror backend/app/schemas/admin_payment.py and
 * backend/app/schemas/refund.py field-for-field. Every money/quantity
 * value is a string here because FastAPI serializes Pydantic Decimal
 * fields as JSON strings, not numbers - parse with Number(...) only for
 * display formatting, never for further math (the backend is the only
 * place a financial total is computed).
 *
 * Refunds are never created from this module - they're created by the
 * backend the moment a paid order is cancelled (see
 * app/services/refund.py's create_refund_if_eligible). This module only
 * reviews/approves/rejects/processes ones that already exist.
 */

export interface AdminPaymentListItem {
  id: number;
  order_id: number;
  order_number: string;
  customer_id: number;
  customer_name: string;
  customer_email: string;
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

export interface AdminPaymentListResponse {
  items: AdminPaymentListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface PaymentTransaction {
  id: number;
  transaction_type: string;
  status: string;
  amount: string;
  currency: string;
  gateway_name: string | null;
  gateway_transaction_id: string | null;
  failure_reason: string | null;
  initiated_at: string;
  completed_at: string | null;
}

export interface AdminRefund {
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

export interface AdminPaymentDetail extends AdminPaymentListItem {
  transactions: PaymentTransaction[];
  refund: AdminRefund | null;
}

export interface AdminRefundListResponse {
  items: AdminRefund[];
  page: number;
  page_size: number;
  total: number;
}

/** Mirrors refund_state.py's REFUND lifecycle - the only actions legal
 * from each status. A customer can never move a refund out of
 * PENDING_APPROVAL; only these ADMIN actions do. */
export function refundActionsFor(status: string): { approve: boolean; reject: boolean; process: boolean } {
  return {
    approve: status === "PENDING_APPROVAL",
    reject: status === "PENDING_APPROVAL",
    process: status === "APPROVED" || status === "FAILED",
  };
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class PaymentsApiError extends Error {
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
    throw new PaymentsApiError(response.status, body?.message ?? "Something went wrong.");
  }
  return response.json();
}

export interface AdminPaymentListParams {
  page?: number;
  page_size?: number;
  status?: string;
  payment_method?: string;
  order_id?: number;
  date_from?: string;
  date_to?: string;
  q?: string;
}

export async function fetchAdminPayments(
  accessToken: string,
  params: AdminPaymentListParams,
): Promise<AdminPaymentListResponse> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  return request(accessToken, `/payments/admin?${search.toString()}`);
}

export async function fetchAdminPaymentDetail(accessToken: string, id: number): Promise<AdminPaymentDetail> {
  return request(accessToken, `/payments/admin/${id}`);
}

export async function fetchAdminRefunds(
  accessToken: string,
  params: { status?: string; page?: number; page_size?: number },
): Promise<AdminRefundListResponse> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  return request(accessToken, `/payments/refunds?${search.toString()}`);
}

export async function approveRefund(accessToken: string, refundId: number): Promise<AdminRefund> {
  return request(accessToken, `/payments/refunds/${refundId}/approve`, { method: "POST" });
}

export async function rejectRefund(accessToken: string, refundId: number, reason: string): Promise<AdminRefund> {
  return request(accessToken, `/payments/refunds/${refundId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason: reason || undefined }),
  });
}

export async function processRefund(accessToken: string, refundId: number): Promise<AdminRefund> {
  return request(accessToken, `/payments/refunds/${refundId}/process`, { method: "POST" });
}
