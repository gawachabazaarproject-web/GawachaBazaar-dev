import React, { useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, TextInput, View } from "react-native";
import { Stack, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { toApiError } from "@/api";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { CheckoutSection } from "@/components/checkout/CheckoutSection";
import { HarvestSlotSelector, slotSummary, Day, Slot } from "@/components/checkout/HarvestSlotSelector";
import { CheckoutStepper } from "@/components/checkout/CheckoutStepper";
import { BasketSummaryCard } from "@/components/checkout/BasketSummaryCard";
import { ImpactCard } from "@/components/checkout/ImpactCard";
import { useCart, useEvaluatePromo } from "@/features/cart/useCart";
import { useAddresses } from "@/features/address/useAddresses";
import { usePlaceOrder, PlaceOrderResult } from "@/features/checkout/useCheckout";
import { useCancelOrder } from "@/features/orders/useOrders";
import { useOnlinePayment } from "@/features/payment/useOnlinePayment";
import { RazorpayCheckout } from "@/components/payment/RazorpayCheckout";
import { formatMoney } from "@/utils/money";
import { colors, spacing } from "@/theme";
import { PaymentMethod, PaymentResponse, PromotionEvaluationResponse, RazorpaySuccessPayload } from "@/types/api";

export default function CheckoutScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { data: cart } = useCart();
  const { data: addresses } = useAddresses();
  const placeOrder = usePlaceOrder();
  const cancelOrder = useCancelOrder();
  const online = useOnlinePayment();

  const [selectedAddressId, setSelectedAddressId] = useState<number | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("COD");
  const [result, setResult] = useState<PlaceOrderResult | null>(null);
  const [day, setDay] = useState<Day>("today");
  const [slot, setSlot] = useState<Slot>("morning");

  const [promoInput, setPromoInput] = useState("");
  const [promoEvaluation, setPromoEvaluation] = useState<PromotionEvaluationResponse | null>(null);
  const evaluatePromo = useEvaluatePromo();

  const handleApplyPromo = () => {
    if (!promoInput.trim()) return;
    evaluatePromo.mutate(promoInput.trim(), { onSuccess: setPromoEvaluation });
  };

  const handleRemovePromo = () => {
    setPromoInput("");
    setPromoEvaluation(null);
  };

  useEffect(() => {
    if (!selectedAddressId && addresses && addresses.length > 0) {
      setSelectedAddressId((addresses.find((a) => a.is_default) ?? addresses[0]).id);
    }
  }, [addresses, selectedAddressId]);

  // An online (Razorpay) payment comes back PROCESSING - the order only
  // counts as placed once Razorpay reports the payment, so open Checkout
  // instead of jumping to the success screen.
  const awaitingOnlinePayment =
    !!result && !result.paymentError && result.payment?.payment_method === "UPI" && result.payment.status !== "PAID";

  useEffect(() => {
    if (!result || result.paymentError) return;
    if (result.payment?.payment_method === "UPI" && result.payment.status !== "PAID") {
      online.start(result.payment.id);
      return;
    }
    router.replace(`/checkout/success?orderId=${result.order.id}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  const handleOnlineSuccess = async (response: RazorpaySuccessPayload) => {
    if (!result) return;
    const payment = await online.complete(response);
    if (payment?.status === "PAID") {
      router.replace(`/checkout/success?orderId=${result.order.id}`);
    } else if (payment) {
      // Paid on Razorpay's side but the capture isn't reported yet - the
      // webhook finishes it; never tell the customer it failed.
      Alert.alert("Payment received", "We're confirming it with your bank. Your order will update automatically in a moment.");
      router.replace(`/order/${result.order.id}`);
    }
    // null -> online.error is shown on the "Complete your payment" screen.
  };

  // Closing the sheet or paying again first re-checks the payment with the
  // backend - it may already be PAID (e.g. the UPI app took the money but
  // the callback never reached us).
  const showSuccessIfPaid = (payment: PaymentResponse | null) => {
    if (payment?.status === "PAID" && result) router.replace(`/checkout/success?orderId=${result.order.id}`);
  };
  const handleOnlineDismiss = async () => showSuccessIfPaid(await online.dismiss());
  const handlePayAgain = async () => {
    if (result) showSuccessIfPaid(await online.retryForOrder(result.order.id));
  };

  const handlePlaceOrder = () => {
    if (!selectedAddressId) return;
    placeOrder.mutate(
      {
        addressId: selectedAddressId,
        paymentMethod,
        promoCode: promoEvaluation?.eligible ? promoEvaluation.applied_code : null,
      },
      { onSuccess: setResult },
    );
  };

  const handleCancelFailedOrder = () => {
    if (!result) return;
    Alert.alert("Cancel this order?", "You can place a new order right away with Cash on Delivery.", [
      { text: "Keep order", style: "cancel" },
      {
        text: "Cancel order",
        style: "destructive",
        onPress: () => {
          cancelOrder.mutate(
            { id: result.order.id, payload: {} },
            { onSuccess: () => setResult(null) },
          );
        },
      },
    ]);
  };

  // The two result screens below must come BEFORE the empty-cart check:
  // placing an order empties the cart, so checking the cart first would
  // hide the payment outcome (and never mount the Razorpay sheet).

  // A payment attempt failed but the order already exists - honest
  // recovery UI rather than pretending nothing happened (brief §28: never
  // fake a payment gateway that doesn't exist).
  if (result?.paymentError) {
    return (
      <Screen>
        <Stack.Screen options={{ headerShown: true, title: "Checkout" }} />
        <View style={styles.centered}>
          <Feather name="alert-circle" size={40} color={colors.error} />
          <Text variant="h2" align="center" style={styles.errorTitle}>
            We couldn't complete your payment
          </Text>
          <Text variant="body" color={colors.textSecondary} align="center" style={styles.errorMessage}>
            {result.paymentError} Your order (#{result.order.order_number}) hasn't been confirmed yet.
          </Text>
          {online.error && online.error !== result.paymentError ? (
            <Text variant="bodySmall" color={colors.error} align="center" style={{ marginTop: spacing.md }}>
              {online.error}
            </Text>
          ) : null}
          {paymentMethod === "UPI" ? (
            <Button
              label="Try paying online again"
              onPress={handlePayAgain}
              loading={online.busy}
              fullWidth
              style={{ marginTop: spacing.xl }}
            />
          ) : null}
          <Button
            label="Cancel order and use Cash on Delivery"
            variant={paymentMethod === "UPI" ? "secondary" : "primary"}
            onPress={handleCancelFailedOrder}
            loading={cancelOrder.isPending}
            fullWidth
            style={{ marginTop: paymentMethod === "UPI" ? spacing.sm : spacing.xl }}
          />
          <Button
            label="View order"
            variant="ghost"
            onPress={() => router.replace(`/order/${result.order.id}`)}
            style={{ marginTop: spacing.sm }}
          />
        </View>
        <RazorpayCheckout checkout={online.checkout} onSuccess={handleOnlineSuccess} onDismiss={handleOnlineDismiss} />
      </Screen>
    );
  }

  if (awaitingOnlinePayment && result?.payment) {
    const payment = result.payment;
    return (
      <Screen>
        <Stack.Screen options={{ headerShown: true, title: "Payment" }} />
        <View style={styles.centered}>
          <Feather name="credit-card" size={40} color={colors.primary} />
          <Text variant="h2" align="center" style={styles.errorTitle}>
            Complete your payment
          </Text>
          <Text variant="body" color={colors.textSecondary} align="center" style={styles.errorMessage}>
            Order #{result.order.order_number} is reserved for you. Pay securely with Razorpay to confirm it.
          </Text>
          {online.error ? (
            <Text variant="bodySmall" color={colors.error} align="center" style={{ marginTop: spacing.md }}>
              {online.error}
            </Text>
          ) : null}
          <Button
            label={`Pay ${formatMoney(payment.amount, payment.currency)}`}
            onPress={handlePayAgain}
            loading={online.busy}
            fullWidth
            style={{ marginTop: spacing.xl }}
          />
          <Button
            label="Cancel order"
            variant="ghost"
            onPress={handleCancelFailedOrder}
            style={{ marginTop: spacing.sm }}
          />
        </View>
        <RazorpayCheckout checkout={online.checkout} onSuccess={handleOnlineSuccess} onDismiss={handleOnlineDismiss} />
      </Screen>
    );
  }

  if (!cart || cart.items.length === 0) {
    return (
      <Screen>
        <Stack.Screen options={{ headerShown: true, title: "Checkout" }} />
        <View style={styles.centered}>
          <Text variant="body" color={colors.textSecondary}>
            Your cart is empty.
          </Text>
        </View>
      </Screen>
    );
  }

  // The evaluated final_total (when a promo is applied) reflects what
  // checkout will actually charge - cart.total_amount never includes a
  // discount, since discounting only ever happens as part of order
  // creation on the backend (see PromotionService.evaluate_for_cart).
  const total = promoEvaluation?.eligible ? promoEvaluation.final_total : cart.total_amount ?? "0";

  return (
    <Screen edges={["top", "bottom"]}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={8} style={styles.headerSide} accessibilityRole="button" accessibilityLabel="Go back">
          <Feather name="chevron-left" size={26} color={colors.textPrimary} />
        </Pressable>
        <Text variant="h1" color={colors.primary} style={{ fontSize: 24 }}>
          Checkout
        </Text>
        <Pressable
          onPress={() => router.push("/account/support")}
          hitSlop={8}
          style={[styles.headerSide, styles.headerRight]}
          accessibilityRole="button"
          accessibilityLabel="Help"
        >
          <Feather name="help-circle" size={24} color={colors.textPrimary} />
        </Pressable>
      </View>

      <View style={styles.trustStrip}>
        <View style={styles.trustItem}>
          <MaterialCommunityIcons name="leaf" size={18} color={colors.success} />
          <Text variant="caption" color={colors.textSecondary} numberOfLines={1} style={{ flexShrink: 1 }}>
            100% Farm Fresh Guarantee
          </Text>
        </View>
        <View style={styles.trustDivider} />
        <View style={styles.trustItem}>
          <MaterialCommunityIcons name="barley" size={18} color={colors.accentDark} />
          <View style={styles.trustPill}>
            <Text variant="caption" color={colors.textPrimary} numberOfLines={1} style={{ fontWeight: "600" }}>
              Direct Mandi Harvest
            </Text>
          </View>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <CheckoutStepper active={1} />
        {/* 1. Delivery address - real */}
        <CheckoutSection
          number={1}
          label="Delivery Address"
          action={
            <Pressable onPress={() => router.push("/address")} style={styles.changeLink} hitSlop={8}>
              <Text variant="bodyMedium" color={colors.primary}>
                Change
              </Text>
              <Feather name="chevron-right" size={16} color={colors.primary} />
            </Pressable>
          }
        >
          {(addresses ?? []).map((address) => {
            const selected = selectedAddressId === address.id;
            return (
              <Pressable
                key={address.id}
                style={[styles.addressCard, selected && styles.addressCardSelected]}
                onPress={() => setSelectedAddressId(address.id)}
                accessibilityRole="radio"
                accessibilityState={{ selected }}
              >
                <View style={styles.addressIcon}>
                  <Feather name="home" size={22} color={colors.primary} />
                </View>
                <View style={{ flex: 1 }}>
                  <View style={styles.addressTitleRow}>
                    <Text variant="h3">{address.label}</Text>
                    {address.is_default ? (
                      <View style={styles.primaryBadge}>
                        <Text variant="label" color={colors.primary}>
                          PRIMARY
                        </Text>
                      </View>
                    ) : null}
                  </View>
                  <Text variant="bodySmall" color={colors.textSecondary} style={{ marginTop: 2 }}>
                    {address.address_line_1}, {address.city}, {address.state} {address.postal_code}
                  </Text>
                </View>
                <Feather name={selected ? "check-circle" : "chevron-right"} size={20} color={selected ? colors.primary : colors.textPrimary} />
              </Pressable>
            );
          })}
          <Pressable onPress={() => router.push("/address/add")} style={styles.addAddressCard} accessibilityRole="button">
            <Feather name="plus-circle" size={20} color={colors.textPrimary} />
            <Text variant="bodyMedium">Add new address</Text>
          </Pressable>
        </CheckoutSection>

        {/* 2. Harvest slot - illustrative, interactive local state (see component) */}
        <CheckoutSection number={2} label="Delivery" badge="FRESH TIMINGS" badgeIcon="feather">
          <HarvestSlotSelector day={day} slot={slot} onDayChange={setDay} onSlotChange={setSlot} />
        </CheckoutSection>

        {/* 3. Payment method - online via Razorpay, or Cash on Delivery */}
        <CheckoutSection
          number={3}
          label="Payment"
          title="Payment Options (पेमेंट)"
          badge="BANK GRADE SSL"
          badgeIcon="lock"
        >
          <PaymentOption
            label="Pay online"
            description="UPI, cards, netbanking & wallets"
            icon="credit-card"
            selected={paymentMethod === "UPI"}
            onPress={() => setPaymentMethod("UPI")}
            extra={<PaymentBrands />}
          />
          <PaymentOption
            label="Cash / UPI on Delivery"
            description="Verify freshness before paying at your door"
            icon="dollar-sign"
            selected={paymentMethod === "COD"}
            onPress={() => setPaymentMethod("COD")}
          />
        </CheckoutSection>

        {/* 4. Promo code - real backend evaluation, never a locally-computed
            discount (see PromotionService.evaluate_for_cart on the backend -
            this screen only ever displays what that call returns). */}
        <CheckoutSection number={4} label="Offers" title="Promo Code">
          {promoEvaluation?.eligible ? (
            <View style={styles.promoAppliedRow}>
              <View style={{ flex: 1 }}>
                <Text variant="bodyMedium" color={colors.success}>
                  {promoEvaluation.applied_code} applied
                </Text>
                <Text variant="caption" color={colors.textSecondary}>
                  {promoEvaluation.message} · You saved {formatMoney(promoEvaluation.discount_amount, cart.currency ?? "INR")}
                </Text>
              </View>
              <Pressable onPress={handleRemovePromo} hitSlop={8}>
                <Feather name="x-circle" size={20} color={colors.textSecondary} />
              </Pressable>
            </View>
          ) : (
            <View style={styles.promoRow}>
              <View style={styles.promoInputWrapper}>
                <Feather name="tag" size={18} color={colors.textSecondary} />
                <TextInput
                  value={promoInput}
                  onChangeText={(text) => {
                    setPromoInput(text.toUpperCase());
                    if (promoEvaluation) setPromoEvaluation(null);
                  }}
                  placeholder="Enter promo code"
                  placeholderTextColor={colors.textMuted}
                  autoCapitalize="characters"
                  style={styles.promoInput}
                />
              </View>
              <Pressable
                style={[styles.promoApplyButton, (!promoInput.trim() || evaluatePromo.isPending) && styles.disabled]}
                onPress={handleApplyPromo}
                disabled={!promoInput.trim() || evaluatePromo.isPending}
              >
                <Text variant="bodyMedium" color={colors.textOnAccent}>
                  {evaluatePromo.isPending ? "Checking..." : "Apply"}
                </Text>
              </Pressable>
            </View>
          )}
          {promoEvaluation && !promoEvaluation.eligible ? (
            <Text variant="caption" color={colors.error} style={{ marginTop: spacing.xs }}>
              {promoEvaluation.message}
            </Text>
          ) : null}
          <View style={styles.offerBanner}>
            <View style={styles.offerIcon}>
              <Feather name="gift" size={20} color={colors.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text variant="bodyMedium">Save more with farm fresh offers!</Text>
              <Text variant="caption" color={colors.textSecondary}>
                Get special discounts and support local farmers.
              </Text>
            </View>
            <Feather name="chevron-right" size={18} color={colors.textPrimary} />
          </View>
        </CheckoutSection>

        {/* 5. Order summary - real cart data */}
        <CheckoutSection number={5} label="Order Summary" title="Review your order">
          <BasketSummaryCard
            items={cart.items}
            totalAmount={cart.total_amount}
            currency={cart.currency}
            slotLabel={slotSummary(day, slot)}
            paymentLabel={paymentMethod === "UPI" ? "Pay online" : "Cash / UPI on Delivery"}
          />
          {promoEvaluation?.eligible ? (
            <View style={styles.discountSummaryRow}>
              <Text variant="bodyMedium" color={colors.textSecondary}>Discount ({promoEvaluation.applied_code})</Text>
              <Text variant="priceSmall" color={colors.success}>
                -{formatMoney(promoEvaluation.discount_amount, cart.currency ?? "INR")}
              </Text>
            </View>
          ) : null}
          <ImpactCard />
          <View style={styles.sustainRow}>
            <MaterialCommunityIcons name="leaf" size={18} color={colors.success} />
            <Text variant="caption" color={colors.textSecondary} style={{ flex: 1 }}>
              Zero single-use plastics. Delivered in sanitised, returnable jute crates.
            </Text>
          </View>
        </CheckoutSection>
      </ScrollView>

      <View style={[styles.footer, { bottom: insets.bottom + spacing.md }]}>
        {paymentMethod === "COD" ? (
          <Text variant="caption" color={colors.textSecondary} style={styles.footerNote}>
            Amount to pay on delivery: {formatMoney(total, cart.currency ?? "INR")}
          </Text>
        ) : null}
        {/* Order creation itself failed (offline, out of stock, ...) - no
            order exists, so say why instead of silently doing nothing. */}
        {placeOrder.error ? (
          <Text variant="caption" color={colors.error} style={styles.footerNote}>
            {toApiError(placeOrder.error).message}
          </Text>
        ) : null}
        <View style={styles.placeOrderBar}>
          <View style={{ flex: 1 }}>
            <View style={styles.totalRow}>
              <Text variant="priceLarge" color={colors.textInverse} style={{ fontSize: 22, lineHeight: 28 }}>
                {formatMoney(total, cart.currency ?? "INR")}
              </Text>
              <View style={styles.totalDivider} />
              <Text variant="bodySmall" color={colors.textInverse}>
                {cart.items.length} {cart.items.length === 1 ? "item" : "items"}
              </Text>
            </View>
            <Text variant="caption" color={colors.primaryLight} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.85}>
              Free delivery • {slotSummary(day, slot)}
            </Text>
          </View>
          <Pressable
            style={[styles.placeOrderButton, (!selectedAddressId || placeOrder.isPending) && styles.disabled]}
            onPress={handlePlaceOrder}
            disabled={!selectedAddressId || placeOrder.isPending}
          >
            <Text variant="bodyMedium" color={colors.textOnAccent}>
              {placeOrder.isPending ? "Placing..." : "Place Order"}
            </Text>
            <Feather name="arrow-right" size={16} color={colors.textOnAccent} />
          </Pressable>
        </View>
      </View>
    </Screen>
  );
}

/** Simple brand marks shown under "Pay online" - plain shapes/text, no
 * trademarked artwork. */
function PaymentBrands() {
  return (
    <View style={styles.brands}>
      <Text variant="caption" style={[styles.brandText, { color: "#1A4FB5", fontStyle: "italic", fontWeight: "800" }]}>
        VISA
      </Text>
      <View style={styles.mc}>
        <View style={[styles.mcDot, { backgroundColor: "#E0443A" }]} />
        <View style={[styles.mcDot, { backgroundColor: "#F2A12B", marginLeft: -7 }]} />
      </View>
      <Text variant="caption" style={[styles.brandText, { color: "#0C6AB0", fontWeight: "800" }]}>
        UPI
      </Text>
      <Text variant="caption" style={[styles.brandText, { color: "#0B7CC4", fontWeight: "800" }]}>
        Paytm
      </Text>
    </View>
  );
}

function PaymentOption({
  label,
  description,
  icon,
  selected,
  onPress,
  extra,
}: {
  label: string;
  description: string;
  icon: keyof typeof Feather.glyphMap;
  selected: boolean;
  onPress: () => void;
  extra?: React.ReactNode;
}) {
  return (
    <Pressable
      style={[styles.paymentOption, selected && styles.paymentOptionSelected]}
      onPress={onPress}
      accessibilityRole="radio"
      accessibilityState={{ selected }}
    >
      <View style={[styles.paymentIcon, selected && styles.paymentIconSelected]}>
        <Feather name={icon} size={20} color={colors.primary} />
      </View>
      <View style={{ flex: 1 }}>
        <Text variant="bodyMedium" style={{ fontWeight: "600" }}>
          {label}
        </Text>
        <Text variant="caption" color={colors.textSecondary}>
          {description}
        </Text>
        {extra}
      </View>
      <View style={[styles.radio, selected && styles.radioActive]}>{selected ? <View style={styles.radioDot} /> : null}</View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.base,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  headerSide: { width: 36, height: 36, justifyContent: "center" },
  headerRight: { alignItems: "flex-end" },
  trustStrip: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.base,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderColor: colors.divider,
    gap: spacing.sm,
  },
  trustItem: { flexDirection: "row", alignItems: "center", gap: 6, flexShrink: 1 },
  trustDivider: { width: 1, height: 20, backgroundColor: colors.border },
  trustPill: { backgroundColor: colors.accentLight, borderRadius: 999, paddingHorizontal: 9, paddingVertical: 4, flexShrink: 1 },
  content: { paddingHorizontal: spacing.base, paddingBottom: 170 },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  errorTitle: { marginTop: spacing.lg },
  errorMessage: { marginTop: spacing.sm },
  changeLink: { flexDirection: "row", alignItems: "center", gap: 2 },
  addressCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: 18,
    backgroundColor: "#EEF0E9",
    borderWidth: 1.5,
    borderColor: "transparent",
    marginBottom: spacing.sm,
  },
  addressCardSelected: { borderColor: colors.primary },
  addressIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  addressTitleRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  primaryBadge: { backgroundColor: colors.primaryLight, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },
  addAddressCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    height: 52,
    borderRadius: 14,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: colors.border,
  },
  radio: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  radioActive: { borderColor: colors.primary, borderWidth: 2 },
  radioDot: { width: 12, height: 12, borderRadius: 6, backgroundColor: colors.primary },
  paymentOption: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.divider,
    backgroundColor: colors.surface,
    marginBottom: spacing.sm,
  },
  paymentOptionSelected: { borderColor: colors.primary, borderWidth: 1.5, backgroundColor: colors.primaryLight },
  paymentIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.divider,
    alignItems: "center",
    justifyContent: "center",
  },
  paymentIconSelected: { backgroundColor: "rgba(47,122,77,0.14)" },
  brands: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginTop: spacing.sm },
  brandText: { fontSize: 13, lineHeight: 16 },
  mc: { flexDirection: "row", alignItems: "center" },
  mcDot: { width: 16, height: 16, borderRadius: 8 },
  promoRow: { flexDirection: "row", gap: spacing.sm },
  promoInputWrapper: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    height: 50,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    borderRadius: 25,
    paddingHorizontal: spacing.base,
  },
  promoInput: { flex: 1, paddingVertical: 0, fontSize: 15, color: colors.textPrimary },
  promoApplyButton: {
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.accent,
    borderRadius: 25,
    paddingHorizontal: spacing.xl,
    height: 50,
  },
  promoAppliedRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.md,
    borderWidth: 1.5,
    borderColor: colors.success,
    backgroundColor: colors.primaryLight,
    borderRadius: 16,
  },
  offerBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: "#EEF0E9",
    borderRadius: 16,
    padding: spacing.md,
    marginTop: spacing.md,
  },
  offerIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  discountSummaryRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.sm,
  },
  sustainRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.md },
  footer: {
    position: "absolute",
    left: spacing.sm,
    right: spacing.sm,
  },
  footerNote: { textAlign: "center", marginBottom: spacing.xs },
  placeOrderBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: colors.primary,
    borderRadius: 30,
    paddingVertical: spacing.sm,
    paddingLeft: spacing.base,
    paddingRight: spacing.sm,
    gap: spacing.sm,
  },
  totalRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  totalDivider: { width: 1, height: 22, backgroundColor: "rgba(255,255,255,0.4)" },
  placeOrderButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.accent,
    borderRadius: 999,
    paddingHorizontal: spacing.base,
    height: 42,
  },
  disabled: { opacity: 0.5 },
});
