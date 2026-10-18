import { useEffect, useRef } from "react";
import { Alert, AppState } from "react-native";
import { useQueryClient } from "@tanstack/react-query";
import { paymentApi, toApiError } from "@/api";
import { forgetPendingCheckout, isUnknownOutcome, readPendingCheckout } from "./pendingCheckout";

const NOT_CONFIRMED = "PAYMENT_NOT_CONFIRMED";

/**
 * On launch and whenever the app returns to the foreground, re-check a
 * checkout whose payment may have gone through without the app hearing about it.
 * The backend asks Razorpay itself, so this needs no proof from the device.
 * Mount once, inside the signed-in part of the app.
 */
export function usePendingPaymentResume() {
  const queryClient = useQueryClient();
  const running = useRef(false);

  useEffect(() => {
    const check = async () => {
      if (running.current) return;
      running.current = true;
      try {
        const sessionId = await readPendingCheckout();
        if (sessionId === null) return;
        try {
          await paymentApi.verifyOnline(sessionId);
          await forgetPendingCheckout();
          queryClient.invalidateQueries({ queryKey: ["cart"] });
          queryClient.invalidateQueries({ queryKey: ["orders"] });
          queryClient.invalidateQueries({ queryKey: ["order"] });
          Alert.alert("Payment received", "Your payment went through and your order has been placed. You can see it in Orders.");
        } catch (err) {
          const apiErr = toApiError(err);
          if (apiErr.code === NOT_CONFIRMED || isUnknownOutcome(apiErr)) return; // keep checking later
          // A definite answer: not ours any more (404), or refunded / could not be placed (409).
          await forgetPendingCheckout();
          if (apiErr.status === 409) Alert.alert("About your payment", apiErr.message);
        }
      } finally {
        running.current = false;
      }
    };

    void check();
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") void check();
    });
    return () => subscription.remove();
  }, [queryClient]);
}
