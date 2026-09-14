import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cartApi, paymentApi, toApiError } from "@/api";
import { OrderDetailResponse, PaymentInitiationResponse, PaymentMethod } from "@/types/api";

export interface PlaceOrderResult {
  order: OrderDetailResponse;
  payment: PaymentInitiationResponse | null;
  /** Set when the order was created successfully but the payment
   * attempt itself failed (e.g. the intentionally-incomplete UPI
   * gateway) - the order still exists and is still PENDING/cancellable,
   * so the UI must not treat this as "nothing happened". */
  paymentError: string | null;
}

/**
 * Checkout is two real backend calls, never one fabricated "place order"
 * endpoint (there isn't one - see PHASE_13/14 API docs): first
 * `POST /cart/checkout` creates a PENDING order from the cart, then
 * `POST /payments` attaches a payment obligation to it. COD confirms the
 * order synchronously. UPI initiation currently always fails, honestly,
 * because the PNB gateway adapter is an intentional placeholder (Phase
 * 14) - this hook never hides that failure behind a fake success; it
 * surfaces the already-created order alongside the payment error so the
 * screen can offer retry/cancel without losing the order reference.
 */
export function usePlaceOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      addressId,
      paymentMethod,
    }: {
      addressId: number;
      paymentMethod: PaymentMethod;
    }): Promise<PlaceOrderResult> => {
      const order = await cartApi.checkout(addressId);
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
