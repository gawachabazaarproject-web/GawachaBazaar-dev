import { AxiosError } from "axios";
import { ApiErrorBody } from "@/types/api";

/**
 * One error shape the rest of the app deals with - screens never inspect
 * a raw AxiosError or HTTP status directly. `code` is preserved from the
 * backend's uniform {code, message, details} contract for
 * debugging/logging; `message` is always safe to show a user directly.
 */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number | null;
  readonly details: unknown;
  /** True for "no response reached the server at all" (offline, timeout, DNS). */
  readonly isNetworkError: boolean;

  constructor(params: {
    message: string;
    code: string;
    status: number | null;
    details?: unknown;
    isNetworkError?: boolean;
  }) {
    super(params.message);
    this.code = params.code;
    this.status = params.status;
    this.details = params.details;
    this.isNetworkError = params.isNetworkError ?? false;
  }
}

const FRIENDLY_BY_STATUS: Record<number, string> = {
  400: "That request wasn't valid. Please check the details and try again.",
  401: "Your session has expired. Please log in again.",
  403: "You don't have permission to do that.",
  404: "We couldn't find what you're looking for.",
  409: "This couldn't be completed because something changed. Please refresh and try again.",
  422: "Please check the details you entered and try again.",
  500: "Something went wrong on our end. Please try again.",
  502: "Something went wrong on our end. Please try again.",
  503: "GawachaBazaar is temporarily unavailable. Please try again shortly.",
};

/** 5xx responses whose backend message was written for customers - the
 * payment-availability outcomes from backend payment.py/handlers.py.
 * Shown as-is; every other 5xx keeps the generic mapping above. */
const CUSTOMER_SAFE_5XX_CODES = new Set([
  "ONLINE_PAYMENTS_NOT_CONFIGURED",
  "PAYMENT_GATEWAY_UNAVAILABLE",
  "PAYMENT_GATEWAY_ERROR",
  "AUTH_UNAVAILABLE",
]);

/** Codes whose backend message is accurate but not customer-friendly
 * (a gateway rejection carries Razorpay's own wording, e.g.
 * "Authentication failed", which means nothing to a shopper). */
const FRIENDLY_BY_CODE: Record<string, string> = {
  PAYMENT_GATEWAY_REJECTED:
    "Online payment couldn't be started right now. Please try again, or choose Cash on Delivery.",
};

/** Maps a raw backend/network failure into a safe, user-facing ApiError.
 * Never surfaces a raw "500 Internal Server Error" or stack trace. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;

  const axiosError = error as AxiosError<ApiErrorBody>;
  if (axiosError?.isAxiosError) {
    if (!axiosError.response) {
      const isTimeout = axiosError.code === "ECONNABORTED";
      return new ApiError({
        message: isTimeout
          ? "That took too long. Please check your connection and try again."
          : "You appear to be offline. Please check your connection and try again.",
        code: isTimeout ? "TIMEOUT" : "NETWORK_ERROR",
        status: null,
        isNetworkError: true,
      });
    }

    const status = axiosError.response.status;
    const body = axiosError.response.data;
    const backendMessage = typeof body?.message === "string" ? body.message : undefined;
    const code = typeof body?.code === "string" ? body.code : undefined;
    const backendMessageIsSafe = status < 500 || (!!code && CUSTOMER_SAFE_5XX_CODES.has(code));
    return new ApiError({
      // Prefer the backend's own message for 4xx (it's already
      // customer-safe per the backend's exception contract) and for the
      // allow-listed payment 5xx codes; fall back to a generic mapping for
      // anything else or if the body is malformed.
      message:
        (code && FRIENDLY_BY_CODE[code]) ??
        (backendMessageIsSafe && backendMessage
          ? backendMessage
          : FRIENDLY_BY_STATUS[status] ?? "Something went wrong. Please try again."),
      code: body?.code ?? `HTTP_${status}`,
      status,
      details: body?.details,
    });
  }

  return new ApiError({
    message: "Something went wrong. Please try again.",
    code: "UNKNOWN_ERROR",
    status: null,
  });
}
