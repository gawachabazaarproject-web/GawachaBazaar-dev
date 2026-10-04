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

export function confirmDelivery(accessToken: string, id: number): Promise<void> {
  return post(accessToken, `/${id}/deliver`);
}
