/**
 * Maps a raw backend status string (order/payment/fulfillment/refund) to a
 * semantic color tone. Every status string here is copied verbatim from
 * the enums in backend/app/services/{order,payment,fulfillment,refund}_state.py
 * - if a status doesn't match, it falls back to "neutral" rather than
 * guessing, so an unrecognized future status never silently reads as
 * "success" or "danger".
 */
export type StatusTone = "success" | "warning" | "danger" | "info" | "neutral";

const TONE_BY_STATUS: Record<string, StatusTone> = {
  // Order (order_state.py)
  PENDING: "warning",
  CONFIRMED: "info",
  COMPLETED: "success",
  CANCELLED: "danger",
  // EXPIRED is shared by Order and Inventory batch status - "danger" fits
  // both (a lapsed payment window and an expired batch are both real
  // problems, not neutral outcomes).
  EXPIRED: "danger",
  // Product/Category/Variant (products.status IN DRAFT/ACTIVE/INACTIVE/ARCHIVED)
  DRAFT: "neutral",
  ACTIVE: "success",
  INACTIVE: "warning",
  ARCHIVED: "neutral",
  // Inventory operational_status (computed - see InventoryService._operational_status)
  IN_STOCK: "success",
  LOW_STOCK: "warning",
  OUT_OF_STOCK: "danger",
  EXPIRING: "warning",
  // Payment (payment_state.py) - PENDING/CANCELLED/EXPIRED reuse the map above
  PROCESSING: "info",
  PAID: "success",
  FAILED: "danger",
  // Fulfillment (fulfillment_state.py)
  PICKING: "warning",
  PACKED: "warning",
  READY_FOR_DELIVERY: "info",
  ASSIGNED: "info",
  OUT_FOR_DELIVERY: "info",
  DELIVERED: "success",
  // Refund (refund_state.py)
  PENDING_APPROVAL: "warning",
  APPROVED: "info",
  REJECTED: "danger",
  REFUNDED: "success",
  // Promotion (promotion_state.py) - ACTIVE/DRAFT/EXPIRED reuse the map above
  SCHEDULED: "info",
  PAUSED: "warning",
  DISABLED: "neutral",
  // PromotionRedemption.status
  APPLIED: "success",
  REVERSED: "neutral",
  // User.status (users/customers) - ACTIVE/INACTIVE reuse the map above
  SUSPENDED: "danger",
};

export function statusTone(status: string): StatusTone {
  return TONE_BY_STATUS[status] ?? "neutral";
}

export function formatStatusLabel(status: string): string {
  return status
    .split("_")
    .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
    .join(" ");
}
