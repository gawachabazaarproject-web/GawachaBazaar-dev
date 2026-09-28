import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { orderApi, paymentApi, toApiError } from "@/api";
import { PaymentCheckoutResponse, PaymentResponse, RazorpaySuccessPayload } from "@/types/api";

/**
 * Drives one online (Razorpay) payment: fetch checkout details -> the
 * <RazorpayCheckout> sheet is shown while `checkout` is set -> hand the
 * success payload to POST /payments/{id}/confirm.
 *
 * `complete` resolves to the payment as the BACKEND now sees it. PAID
 * means done; PROCESSING means Razorpay hasn't reported the capture yet -
 * the webhook will finish it, so the UI should show "confirming", never
 * "failed".
 */
export function useOnlinePayment() {
  const queryClient = useQueryClient();
  const [checkout, setCheckout] = useState<PaymentCheckoutResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = async (paymentId: number) => {
    setError(null);
    setBusy(true);
    try {
      setCheckout(await paymentApi.checkout(paymentId));
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setBusy(false);
    }
  };

  const complete = async (result: RazorpaySuccessPayload): Promise<PaymentResponse | null> => {
    const current = checkout;
    setCheckout(null);
    if (!current) return null;
    setBusy(true);
    setError(null);
    try {
      return await paymentApi.confirm(current.payment_id, result);
    } catch (err) {
      setError(toApiError(err).message);
      return null;
    } finally {
      setBusy(false);
      refreshOrders();
    }
  };

  /** Ask the backend to re-check this payment with Razorpay (POST
   * /payments/{id}/verify - the backend never trusts a client-reported
   * status). A payment can succeed without the sheet ever reporting it:
   * UPI-app hand-offs lose the callback, the app gets killed mid-payment.
   * Null when the check itself failed - the state is then just unknown. */
  const reconcile = async (paymentId: number): Promise<PaymentResponse | null> => {
    try {
      return await paymentApi.verify(paymentId);
    } catch {
      return null;
    }
  };

  /** After a failed online attempt (e.g. Razorpay was unreachable): start a
   * fresh attempt for this order's payment and open Checkout. An attempt
   * that is still awaiting the customer is re-checked first (it may have
   * been paid already) and otherwise re-opened. Resolves to the payment as
   * the backend now sees it - PAID means there is nothing left to pay. */
  const retryForOrder = async (orderId: number): Promise<PaymentResponse | null> => {
    setError(null);
    setBusy(true);
    try {
      let payment: PaymentResponse = await orderApi.getPayment(orderId);
      if (payment.status === "PROCESSING") payment = (await reconcile(payment.id)) ?? payment;
      else payment = await paymentApi.retry(payment.id);
      if (payment.status !== "PAID") setCheckout(await paymentApi.checkout(payment.id));
      return payment;
    } catch (err) {
      setError(toApiError(err).message);
      return null;
    } finally {
      setBusy(false);
      refreshOrders();
    }
  };

  // Both the orders list and every per-order query (["order", id, ...]).
  const refreshOrders = () => {
    queryClient.invalidateQueries({ queryKey: ["orders"] });
    queryClient.invalidateQueries({ queryKey: ["order"] });
  };

  /** The sheet closed without a success callback - which does not mean the
   * customer didn't pay, so re-check before the screen says "not paid". */
  const dismiss = async (): Promise<PaymentResponse | null> => {
    const current = checkout;
    setCheckout(null);
    if (!current) return null;
    setBusy(true);
    try {
      return await reconcile(current.payment_id);
    } finally {
      setBusy(false);
      refreshOrders();
    }
  };

  return { checkout, busy, error, start, complete, retryForOrder, dismiss };
}
