import { useEffect, useRef } from "react";
import { buildCheckoutOptions, isRazorpaySuccess, RAZORPAY_CHECKOUT_SCRIPT } from "@/features/payment/razorpayOptions";
import { RazorpayCheckoutParams, RazorpaySuccessPayload } from "@/types/api";

interface Props {
  checkout: RazorpayCheckoutParams | null;
  onSuccess: (result: RazorpaySuccessPayload) => void;
  onDismiss: () => void;
}

type RazorpayConstructor = new (options: Record<string, unknown>) => { open: () => void };

let scriptPromise: Promise<void> | null = null;

function loadCheckoutScript(): Promise<void> {
  if ((window as unknown as { Razorpay?: unknown }).Razorpay) return Promise.resolve();
  if (!scriptPromise) {
    scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = RAZORPAY_CHECKOUT_SCRIPT;
      script.onload = () => resolve();
      script.onerror = () => {
        scriptPromise = null;
        reject(new Error("Could not load Razorpay Checkout."));
      };
      document.body.appendChild(script);
    });
  }
  return scriptPromise;
}

/** Web build: Razorpay's own checkout.js overlay, same contract as the
 * native WebView version (RazorpayCheckout.tsx). */
export function RazorpayCheckout({ checkout, onSuccess, onDismiss }: Props) {
  // Latest callbacks without re-opening the overlay on every render.
  const callbacks = useRef({ onSuccess, onDismiss });
  callbacks.current = { onSuccess, onDismiss };

  useEffect(() => {
    if (!checkout) return;
    let cancelled = false;
    loadCheckoutScript()
      .then(() => {
        if (cancelled) return;
        const Razorpay = (window as unknown as { Razorpay: RazorpayConstructor }).Razorpay;
        new Razorpay({
          ...buildCheckoutOptions(checkout),
          handler: (response: unknown) => {
            if (isRazorpaySuccess(response)) callbacks.current.onSuccess(response);
          },
          modal: { ondismiss: () => callbacks.current.onDismiss(), confirm_close: true },
        }).open();
      })
      .catch(() => callbacks.current.onDismiss());
    return () => {
      cancelled = true;
    };
  }, [checkout]);

  return null;
}
