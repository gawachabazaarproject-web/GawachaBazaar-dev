import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { paymentApi, toApiError } from "@/api";
import { OnlineCheckoutCompleteResponse, OnlineCheckoutResponse, RazorpaySuccessPayload } from "@/types/api";
import { forgetPendingCheckout, isUnknownOutcome, rememberPendingCheckout } from "./pendingCheckout";

/** The backend has not seen the capture yet (Razorpay can lag a moment). */
const NOT_CONFIRMED = "PAYMENT_NOT_CONFIRMED";
const CONFIRM_ATTEMPTS = 4;
const CONFIRM_RETRY_MS = 2000;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Pay-first online checkout: Razorpay opens BEFORE any order exists.
 *
 *   start(address, promo) -> backend prices the cart and creates the Razorpay
 *                            order (no order, cart untouched) -> `checkout` is
 *                            set and <RazorpayCheckout> shows the sheet
 *   complete(payload)     -> the sheet reported success -> the backend
 *                            verifies it with Razorpay and only then places
 *                            the order
 *   dismiss()             -> the sheet closed without success: nothing was
 *                            created. Re-checks once in case the money moved
 *                            anyway (UPI app hand-offs lose the callback).
 *
 * `complete` resolves to the placed order, "pending" when Razorpay has not
 * reported the capture yet (the webhook will place the order - never tell the
 * customer it failed), or null on error (see `error`).
 */
export function useOnlineCheckout() {
  const queryClient = useQueryClient();
  const [checkout, setCheckout] = useState<OnlineCheckoutResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["cart"] });
    queryClient.invalidateQueries({ queryKey: ["orders"] });
    queryClient.invalidateQueries({ queryKey: ["order"] });
    queryClient.invalidateQueries({ queryKey: ["bazaar"] });
  };

  const start = async (addressId: number, promoCode?: string | null) => {
    setError(null);
    setBusy(true);
    try {
      const started = await paymentApi.startOnline(addressId, promoCode);
      // Remember it before the sheet opens: if the app dies mid-payment the
      // next launch re-checks this session (see usePendingPaymentResume).
      await rememberPendingCheckout(started.session_id);
      setCheckout(started);
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setBusy(false);
    }
  };

  const complete = async (payload: RazorpaySuccessPayload): Promise<OnlineCheckoutCompleteResponse | "pending" | null> => {
    const current = checkout;
    setCheckout(null);
    if (!current) return null;
    setBusy(true);
    setError(null);
    try {
      for (let attempt = 1; ; attempt++) {
        try {
          const done = await paymentApi.confirmOnline(current.session_id, payload);
          await forgetPendingCheckout();
          return done;
        } catch (err) {
          const apiErr = toApiError(err);
          // Razorpay already reported success, so "not confirmed yet", offline,
          // timeouts, 5xx and an expired sign-in all mean "unknown", never
          // "failed": keep trying, then hand over to the background re-check.
          if (apiErr.code !== NOT_CONFIRMED && !isUnknownOutcome(apiErr)) throw err;
          if (attempt >= CONFIRM_ATTEMPTS) return "pending";
          await sleep(CONFIRM_RETRY_MS);
        }
      }
    } catch (err) {
      // A definite answer from the backend (e.g. refunded because the order
      // could not be placed) - show its message.
      await forgetPendingCheckout();
      setError(toApiError(err).message);
      return null;
    } finally {
      setBusy(false);
      refresh();
    }
  };

  const dismiss = async (): Promise<OnlineCheckoutCompleteResponse | null> => {
    const current = checkout;
    setCheckout(null);
    if (!current) return null;
    setBusy(true);
    try {
      const done = await paymentApi.verifyOnline(current.session_id);
      await forgetPendingCheckout();
      return done;
    } catch (err) {
      const apiErr = toApiError(err);
      if (apiErr.code === NOT_CONFIRMED) return null; // the normal "closed the sheet" case; stays remembered
      if (isUnknownOutcome(apiErr)) {
        // We could not ask: do not pretend nothing happened.
        setError("We couldn't check your payment just now. If money was deducted, your order will appear in Orders shortly.");
      } else {
        await forgetPendingCheckout();
        setError(apiErr.message);
      }
      return null;
    } finally {
      setBusy(false);
      refresh();
    }
  };

  /** Forget a previous attempt's error (e.g. when the shopper switches payment method). */
  const clearError = () => setError(null);

  return { checkout, busy, error, start, complete, dismiss, clearError };
}
