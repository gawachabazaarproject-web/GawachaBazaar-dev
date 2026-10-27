/** Turns a push payload into an in-app route. Pure, so it is easy to reason
 * about: anything malformed returns null and the tap is simply ignored.
 *
 * Payload contract (backend/app/services/push.py): { type, orderId }.
 * `type` is optional for older backend versions; `orderId` alone still routes. */

const ORDER_TYPES = new Set([
  "ORDER_PLACED",
  "ORDER_CONFIRMED",
  "ORDER_PACKED",
  "OUT_FOR_DELIVERY",
  "ORDER_DELIVERED",
  "ORDER_CANCELLED",
  "PAYMENT_RECEIVED",
  "REFUND_INITIATED",
  "REFUND_COMPLETED",
  "DELIVERY_OTP",
]);

export function parseOrderId(raw: unknown): number | null {
  const n = typeof raw === "string" && /^\d{1,12}$/.test(raw) ? Number(raw) : raw;
  return typeof n === "number" && Number.isSafeInteger(n) && n > 0 ? n : null;
}

export function notificationRoute(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const { type, orderId } = data as { type?: unknown; orderId?: unknown };
  if (type !== undefined && (typeof type !== "string" || !ORDER_TYPES.has(type))) return null;
  const id = parseOrderId(orderId);
  return id === null ? null : `/order/${id}`;
}
