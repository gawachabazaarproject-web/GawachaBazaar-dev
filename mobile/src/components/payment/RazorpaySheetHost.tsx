import React, { useEffect, useMemo } from "react";
import { ActivityIndicator, BackHandler, KeyboardAvoidingView, Linking, Platform, StyleSheet, View } from "react-native";
import { WebView, WebViewMessageEvent } from "react-native-webview";
import {
  buildCheckoutOptions,
  isRazorpaySuccess,
  RAZORPAY_CHECKOUT_SCRIPT,
  toInlineScriptJson,
} from "@/features/payment/razorpayOptions";
import { usePaymentSheetStore } from "@/store/paymentSheetStore";
import { colors } from "@/theme";
import { PaymentCheckoutResponse } from "@/types/api";

/**
 * Renders once, at the root layout, over every screen: the Razorpay
 * Checkout sheet opened by <RazorpayCheckout>. It lives in the app's own
 * window so the keyboard shrinks it (KeyboardAvoidingView) and Checkout
 * scrolls the focused card / UPI field into view. `webview_intent` lets
 * Checkout hand UPI payments to installed apps (GPay, PhonePe, ...); those
 * app links are opened with Linking instead of inside the WebView.
 */
export function RazorpaySheetHost() {
  const { checkout, handlers } = usePaymentSheetStore();
  const html = useMemo(() => (checkout ? checkoutPage(checkout) : null), [checkout]);

  // Hardware back closes the sheet, as a Modal's onRequestClose did.
  useEffect(() => {
    if (!handlers) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      handlers.current.onDismiss();
      return true;
    });
    return () => sub.remove();
  }, [handlers]);

  if (!html || !handlers) return null;

  const handleMessage = (event: WebViewMessageEvent) => {
    let message: { type?: string; data?: unknown };
    try {
      message = JSON.parse(event.nativeEvent.data);
    } catch {
      return;
    }
    if (message.type === "success" && isRazorpaySuccess(message.data)) handlers.current.onSuccess(message.data);
    else if (message.type === "dismiss") handlers.current.onDismiss();
  };

  return (
    <KeyboardAvoidingView
      style={styles.sheet}
      // iOS's WKWebView scrolls the focused field above the keyboard itself.
      behavior={Platform.OS === "android" ? "padding" : undefined}
    >
      <WebView
        source={{ html, baseUrl: "https://checkout.razorpay.com" }}
        originWhitelist={["*"]}
        javaScriptEnabled
        domStorageEnabled
        onMessage={handleMessage}
        onShouldStartLoadWithRequest={(request) => {
          if (/^https?:|^about:|^data:/i.test(request.url)) return true;
          // upi://, intent://, tez://, phonepe://, paytmmp:// ...
          Linking.openURL(request.url).catch(() => undefined);
          return false;
        }}
        startInLoadingState
        renderLoading={() => (
          <View style={styles.loading}>
            <ActivityIndicator color={colors.primary} />
          </View>
        )}
        style={styles.webview}
      />
    </KeyboardAvoidingView>
  );
}

function checkoutPage(checkout: PaymentCheckoutResponse): string {
  const options = toInlineScriptJson({ ...buildCheckoutOptions(checkout), webview_intent: true });
  return `<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;background:${colors.background}">
<script src="${RAZORPAY_CHECKOUT_SCRIPT}"></script>
<script>
  function send(type, data) { window.ReactNativeWebView.postMessage(JSON.stringify({ type: type, data: data })); }
  var options = ${options};
  options.handler = function (response) { send("success", response); };
  options.modal = { ondismiss: function () { send("dismiss"); }, confirm_close: true };
  var checkout = new Razorpay(options);
  checkout.open();
</script>
</body></html>`;
}

const styles = StyleSheet.create({
  sheet: { ...StyleSheet.absoluteFill, backgroundColor: colors.background },
  webview: { flex: 1, backgroundColor: colors.background },
  loading: { ...StyleSheet.absoluteFill, alignItems: "center", justifyContent: "center" },
});
