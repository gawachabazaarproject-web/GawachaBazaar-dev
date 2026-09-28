const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export interface DashboardTiles {
  orders_today: number;
  collected_today: string;
  currency: string;
  to_fulfil: number;
  out_for_delivery: number;
  delivered_today: number;
  cancelled_today: number;
}

export interface DashboardAttentionOrder {
  order_id: number;
  order_number: string;
  reason: string;
  since: string;
  total_amount: string;
}

export interface DashboardLowStock {
  variant_id: number;
  product_name: string;
  variant_name: string;
  unit: string;
  available: string;
}

export interface DashboardDeliveryIssue {
  fulfillment_id: number;
  order_id: number;
  order_number: string;
  status: string;
  since: string;
  delivery_partner_name: string | null;
}

/** GET /dashboard - every number computed live by the backend
 * (app/services/dashboard.py); "today" is the IST business day. */
export interface DashboardSummary {
  generated_at: string;
  day_start: string;
  tiles: DashboardTiles;
  refunds_pending_approval: number;
  attention: DashboardAttentionOrder[];
  low_stock_count: number;
  low_stock: DashboardLowStock[];
  delivery_issues: DashboardDeliveryIssue[];
}

export class DashboardApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function fetchDashboard(accessToken: string): Promise<DashboardSummary> {
  const response = await fetch(`${API_BASE_URL}/dashboard`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new DashboardApiError(response.status, body?.message ?? "Unable to load the dashboard.");
  }
  return response.json();
}
