import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cartApi, paymentApi, toApiError } from "@/api";
import { OrderDetailResponse, PaymentInitiationResponse, PaymentMethod } from "@/types/api";

export interface PlaceOrderResult {
  order: OrderDetailResponse;
  payment: PaymentInitiationResponse | null;
  /** Set when the order was created successfully but the payment
   * attempt itself failed (e.g. online payments unavailable, or the
   * gateway didn't respond) - the order still exists and is still
   * PENDING/cancellable, so the UI must not treat this as "nothing
   * happened". */
  paymentError: string | null;
}

/**
 * Checkout is two real backend calls, never one fabricated "place order"
 * endpoint (there isn't one - see PHASE_13/14 API docs): first
 * `POST /cart/checkout` creates a PENDING order from the cart, then
 * `POST /payments` attaches a payment obligation to it. COD confirms the
 * order synchronously. Online payment ("UPI" method, via Razorpay) comes
 * back PROCESSING with a Razorpay order attached - the screen then opens
 * Razorpay Checkout (see useOnlinePayment). A failed initiation is never
 * hidden behind a fake success: the already-created order is surfaced
 * alongside the error so the screen can offer retry/cancel.
 */
export function usePlaceOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      addressId,
      paymentMethod,
      promoCode,
    }: {
      addressId: number;
      paymentMethod: PaymentMethod;
      promoCode?: string | null;
    }): Promise<PlaceOrderResult> => {
      const order = await cartApi.checkout(addressId, promoCode);
      try {
        const payment = await paymentApi.create({ order_id: order.id, payment_method: paymentMethod });
        return { order, payment, paymentError: null };
      } catch (err) {
        return { order, payment: null, paymentError: toApiError(err).message };
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cart"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}
