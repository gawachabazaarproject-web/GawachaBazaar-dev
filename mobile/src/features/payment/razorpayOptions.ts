import { colors } from "@/theme";
import { RazorpayCheckoutParams, RazorpaySuccessPayload } from "@/types/api";

export const RAZORPAY_CHECKOUT_SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";

/** Razorpay Standard Checkout options for one payment. Everything here
 * comes from GET /payments/{id}/checkout - amount and order id are
 * server-authoritative, never computed on the device. */
export function buildCheckoutOptions(checkout: RazorpayCheckoutParams) {
  return {
    key: checkout.key_id,
    order_id: checkout.gateway_order_id,
    amount: checkout.amount_minor,
    currency: checkout.currency,
    name: checkout.merchant_name,
    description: checkout.description,
    prefill: {
      name: checkout.customer_name,
      email: checkout.customer_email,
      contact: checkout.customer_phone,
    },
    theme: { color: colors.primary },
    // A failed attempt keeps the sheet open so the customer can try another
    // method against the same order - see backend razorpay_gateway.py.
    retry: { enabled: true },
  };
}

/** JSON safe to inline inside a <script> tag: `<` is escaped so a value
 * like a customer name can never close the tag early. */
export function toInlineScriptJson(value: unknown): string {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}

export function isRazorpaySuccess(value: unknown): value is RazorpaySuccessPayload {
  const v = value as Partial<RazorpaySuccessPayload> | null;
  return (
    !!v &&
    typeof v.razorpay_order_id === "string" &&
    typeof v.razorpay_payment_id === "string" &&
    typeof v.razorpay_signature === "string"
  );
}
