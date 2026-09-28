import { MutableRefObject } from "react";
import { create } from "zustand";
import { PaymentCheckoutResponse, RazorpaySuccessPayload } from "@/types/api";

export interface PaymentSheetHandlers {
  onSuccess: (result: RazorpaySuccessPayload) => void;
  onDismiss: () => void;
}

interface PaymentSheetState {
  checkout: PaymentCheckoutResponse | null;
  /** A ref, so the screen's latest handlers are used without re-opening. */
  handlers: MutableRefObject<PaymentSheetHandlers> | null;
  open: (checkout: PaymentCheckoutResponse, handlers: MutableRefObject<PaymentSheetHandlers>) => void;
  /** Closes only if `checkout` is still the one showing. */
  close: (checkout: PaymentCheckoutResponse) => void;
}

/** The one Razorpay Checkout sheet, rendered by RazorpaySheetHost at the
 * root layout (see RazorpayCheckout.tsx for why it isn't a Modal). */
export const usePaymentSheetStore = create<PaymentSheetState>((set) => ({
  checkout: null,
  handlers: null,
  open: (checkout, handlers) => set({ checkout, handlers }),
  close: (checkout) => set((state) => (state.checkout === checkout ? { checkout: null, handlers: null } : state)),
}));
