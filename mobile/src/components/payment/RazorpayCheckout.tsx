import { useEffect, useRef } from "react";
import { PaymentSheetHandlers, usePaymentSheetStore } from "@/store/paymentSheetStore";
import { RazorpayCheckoutParams, RazorpaySuccessPayload } from "@/types/api";

interface Props {
  /** The sheet is open while this is set. */
  checkout: RazorpayCheckoutParams | null;
  onSuccess: (result: RazorpaySuccessPayload) => void;
  onDismiss: () => void;
}

/**
 * Native (iOS/Android): opens Razorpay Standard Checkout, which
 * RazorpaySheetHost renders in a WebView over the whole app - works in
 * Expo Go and standalone builds alike, no native Razorpay SDK. See
 * RazorpayCheckout.web.tsx for the web build.
 *
 * Not a <Modal>: on Android a Modal is its own edge-to-edge dialog window,
 * which the keyboard doesn't resize and which gets no keyboard events, so
 * the card / UPI fields ended up hidden behind the keyboard.
 */
export function RazorpayCheckout({ checkout, onSuccess, onDismiss }: Props) {
  const handlers = useRef<PaymentSheetHandlers>({ onSuccess, onDismiss });
  handlers.current = { onSuccess, onDismiss };

  useEffect(() => {
    if (!checkout) return;
    usePaymentSheetStore.getState().open(checkout, handlers);
    return () => usePaymentSheetStore.getState().close(checkout);
  }, [checkout]);

  return null;
}
