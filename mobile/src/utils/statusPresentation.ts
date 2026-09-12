import { colors } from "@/theme";
import { FulfillmentStatus, OrderStatus, PaymentStatus, RefundStatus } from "@/types/api";

/**
 * Presentation-only mapping from backend state to UI. This file makes NO
 * decisions about what is legal/possible - the backend is the sole
 * authority on order/payment/fulfillment/refund state machines (Phase
 * 13-18). If the backend returns a status this file doesn't recognize,
 * every mapping below falls back to a neutral, honest default rather than
 * guessing.
 */

export interface StatusPresentation {
  label: string;
  color: string;
  backgroundColor: string;
}

const NEUTRAL: StatusPresentation = {
  label: "Unknown",
  color: colors.textSecondary,
  backgroundColor: colors.divider,
};

export function presentOrderStatus(status: OrderStatus | string): StatusPresentation {
  switch (status) {
    case "PENDING":
      return { label: "Payment pending", color: colors.warning, backgroundColor: colors.warningLight };
    case "CONFIRMED":
      return { label: "Confirmed", color: colors.info, backgroundColor: colors.infoLight };
    case "COMPLETED":
      return { label: "Delivered", color: colors.success, backgroundColor: colors.successLight };
    case "CANCELLED":
      return { label: "Cancelled", color: colors.error, backgroundColor: colors.errorLight };
    case "EXPIRED":
      return { label: "Expired", color: colors.textMuted, backgroundColor: colors.divider };
    default:
      return NEUTRAL;
  }
}

export function presentFulfillmentStatus(status: FulfillmentStatus | string): StatusPresentation {
  switch (status) {
    case "PENDING":
      return { label: "Order received", color: colors.info, backgroundColor: colors.infoLight };
    case "PICKING":
      return { label: "Being picked", color: colors.info, backgroundColor: colors.infoLight };
    case "PACKED":
      return { label: "Packed", color: colors.info, backgroundColor: colors.infoLight };
    case "READY_FOR_DELIVERY":
      return { label: "Ready for dispatch", color: colors.info, backgroundColor: colors.infoLight };
    case "ASSIGNED":
      return { label: "Delivery assigned", color: colors.primary, backgroundColor: colors.primaryLight };
    case "OUT_FOR_DELIVERY":
      return { label: "Out for delivery", color: colors.accent, backgroundColor: colors.accentLight };
    case "DELIVERED":
      return { label: "Delivered", color: colors.success, backgroundColor: colors.successLight };
    default:
      return NEUTRAL;
  }
}

export function presentPaymentStatus(status: PaymentStatus | string): StatusPresentation {
  switch (status) {
    case "PENDING":
      return { label: "Payment pending", color: colors.warning, backgroundColor: colors.warningLight };
    case "PROCESSING":
      return { label: "Processing payment", color: colors.info, backgroundColor: colors.infoLight };
    case "PAID":
      return { label: "Paid", color: colors.success, backgroundColor: colors.successLight };
    case "FAILED":
      return { label: "Payment failed", color: colors.error, backgroundColor: colors.errorLight };
    case "CANCELLED":
      return { label: "Payment cancelled", color: colors.textMuted, backgroundColor: colors.divider };
    case "EXPIRED":
      return { label: "Payment expired", color: colors.textMuted, backgroundColor: colors.divider };
    default:
      return NEUTRAL;
  }
}

export function presentRefundStatus(status: RefundStatus | string): StatusPresentation {
  switch (status) {
    case "PENDING_APPROVAL":
      return { label: "Pending approval", color: colors.warning, backgroundColor: colors.warningLight };
    case "APPROVED":
      return { label: "Approved", color: colors.info, backgroundColor: colors.infoLight };
    case "PROCESSING":
      return { label: "Processing", color: colors.info, backgroundColor: colors.infoLight };
    case "REFUNDED":
      return { label: "Refunded", color: colors.success, backgroundColor: colors.successLight };
    case "REJECTED":
      return { label: "Rejected", color: colors.error, backgroundColor: colors.errorLight };
    case "FAILED":
      return { label: "Refund failed", color: colors.error, backgroundColor: colors.errorLight };
    default:
      return NEUTRAL;
  }
}

/** Orders considered "active" for the Orders screen's Active/Previous
 * split - purely a UI grouping, not a backend concept. */
export function isActiveOrder(status: OrderStatus | string): boolean {
  return status === "PENDING" || status === "CONFIRMED";
}

/** The backend's own cancel endpoint is the actual authority (it will
 * 409 if illegal) - this only controls whether the app SHOWS the Cancel
 * action, as a UX convenience so the customer doesn't reach a dead end.
 * Mirrors order_state.py's transition table: cancellable from PENDING or
 * CONFIRMED, never from COMPLETED/EXPIRED/CANCELLED. */
export function isOrderCancellable(status: OrderStatus | string): boolean {
  return status === "PENDING" || status === "CONFIRMED";
}
