import React, { useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, TextInput, View } from "react-native";
import { Stack, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { CheckoutSection } from "@/components/checkout/CheckoutSection";
import { HarvestSlotSelector } from "@/components/checkout/HarvestSlotSelector";
import { BasketSummaryCard } from "@/components/checkout/BasketSummaryCard";
import { ImpactCard } from "@/components/checkout/ImpactCard";
import { useCart, useEvaluatePromo } from "@/features/cart/useCart";
import { useAddresses } from "@/features/address/useAddresses";
import { usePlaceOrder, PlaceOrderResult } from "@/features/checkout/useCheckout";
import { useCancelOrder } from "@/features/orders/useOrders";
import { formatMoney } from "@/utils/money";
import { colors, radius, spacing } from "@/theme";
import { PaymentMethod, PromotionEvaluationResponse } from "@/types/api";

export default function CheckoutScreen() {
  const router = useRouter();
  const { data: cart } = useCart();
  const { data: addresses } = useAddresses();
  const placeOrder = usePlaceOrder();
  const cancelOrder = useCancelOrder();

  const [selectedAddressId, setSelectedAddressId] = useState<number | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("COD");
  const [result, setResult] = useState<PlaceOrderResult | null>(null);

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

  useEffect(() => {
    if (result && !result.paymentError) {
      router.replace(`/checkout/success?orderId=${result.order.id}`);
    }
  }, [result, router]);

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
          <Button
            label="Cancel order and use Cash on Delivery"
            onPress={handleCancelFailedOrder}
            loading={cancelOrder.isPending}
            fullWidth
            style={{ marginTop: spacing.xl }}
          />
          <Button
            label="View order"
            variant="ghost"
            onPress={() => router.replace(`/order/${result.order.id}`)}
            style={{ marginTop: spacing.sm }}
          />
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
        <Pressable onPress={() => router.back()} hitSlop={8}>
          <Feather name="arrow-left" size={20} color={colors.textPrimary} />
        </Pressable>
        <Text variant="h3">Checkout</Text>
        <View style={styles.headerRight}>
          <Image source={require("../../assets/logo.jpeg")} style={styles.headerLogo} contentFit="cover" />
          <Pressable onPress={() => router.push("/account/support")} hitSlop={8}>
            <Feather name="help-circle" size={20} color={colors.textSecondary} />
          </Pressable>
        </View>
      </View>

      <View style={styles.trustStrip}>
        <View style={styles.trustItem}>
          <Feather name="shield" size={13} color={colors.success} />
          <Text variant="caption" color={colors.textSecondary}>
            100% Farm Fresh Guarantee
          </Text>
        </View>
        <View style={styles.trustPill}>
          <Text variant="label" color={colors.accentDark}>
            DIRECT MANDI HARVEST
          </Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* 1. Delivery address - real */}
        <CheckoutSection number={1} label="Address" title="Delivery Address (पत्ता)">
          {(addresses ?? []).map((address) => (
            <Pressable key={address.id} style={styles.addressOption} onPress={() => setSelectedAddressId(address.id)}>
              <View style={[styles.radio, selectedAddressId === address.id && styles.radioActive]}>
                {selectedAddressId === address.id ? <View style={styles.radioDot} /> : null}
              </View>
              <View style={{ flex: 1 }}>
                <View style={styles.addressTitleRow}>
                  <Text variant="bodyMedium">{address.label}</Text>
                  {address.is_default ? (
                    <View style={styles.primaryBadge}>
                      <Text variant="label" color={colors.primary}>
                        PRIMARY
                      </Text>
                    </View>
                  ) : null}
                </View>
                <Text variant="bodySmall" color={colors.textSecondary}>
                  {address.address_line_1}, {address.city}, {address.state} {address.postal_code}
                </Text>
              </View>
            </Pressable>
          ))}
          <Pressable onPress={() => router.push("/address/add")} style={styles.addAddressLink}>
            <Feather name="plus" size={14} color={colors.primary} />
            <Text variant="bodyMedium" color={colors.primary} style={{ marginLeft: spacing.xs }}>
              Add new address
            </Text>
          </Pressable>
        </CheckoutSection>

        {/* 2. Harvest slot - illustrative, interactive local state (see component) */}
        <CheckoutSection number={2} label="Delivery" title="Select Farm Harvest Slot" badge="FRESH TIMINGS">
          <HarvestSlotSelector />
        </CheckoutSection>

        {/* 3. Payment method - real (COD/UPI only, matching Phase 14) */}
        <CheckoutSection number={3} label="Payment" title="Payment Options (पेमेंट)" badge="BANK GRADE SSL">
          <PaymentOption
            label="UPI"
            description="Google Pay, PhonePe, Paytm & more"
            icon="smartphone"
            selected={paymentMethod === "UPI"}
            onPress={() => setPaymentMethod("UPI")}
          />
          <PaymentOption
            label="Cash / UPI on Crate Delivery"
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
                <Feather name="tag" size={16} color={colors.textSecondary} />
                <TextInput
                  value={promoInput}
                  onChangeText={(text) => {
                    setPromoInput(text.toUpperCase());
                    if (promoEvaluation) setPromoEvaluation(null);
                  }}
                  placeholder="Enter promo code"
                  placeholderTextColor={colors.textSecondary}
                  autoCapitalize="characters"
                  style={styles.promoInput}
                />
              </View>
              <Pressable
                style={[styles.promoApplyButton, (!promoInput.trim() || evaluatePromo.isPending) && styles.placeOrderButtonDisabled]}
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
        </CheckoutSection>

        {/* 5. Order summary - real cart data */}
        <CheckoutSection number={5} label="Order Summary" title="Review your order">
          <BasketSummaryCard items={cart.items} totalAmount={cart.total_amount} currency={cart.currency} />
          {promoEvaluation?.eligible ? (
            <View style={styles.discountSummaryRow}>
              <Text variant="bodyMedium" color={colors.textSecondary}>Discount ({promoEvaluation.applied_code})</Text>
              <Text variant="bodyMedium" color={colors.success}>
                -{formatMoney(promoEvaluation.discount_amount, cart.currency ?? "INR")}
              </Text>
            </View>
          ) : null}
          <ImpactCard />
          <Text variant="caption" color={colors.textSecondary} align="center" style={styles.sustainabilityNote}>
            Zero single-use plastics. Delivered in sanitised returnable jute crates.
          </Text>
        </CheckoutSection>
      </ScrollView>

      <View style={styles.footer}>
        {paymentMethod === "COD" ? (
          <Text variant="caption" color={colors.textSecondary} style={styles.footerNote}>
            Amount to pay on delivery: {formatMoney(total, cart.currency ?? "INR")}
          </Text>
        ) : null}
        <View style={styles.placeOrderBar}>
          <View>
            <Text variant="price" color={colors.textInverse}>
              {formatMoney(total, cart.currency ?? "INR")}
            </Text>
            <Text variant="caption" color={colors.primaryLight}>
              Free delivery
            </Text>
          </View>
          <Pressable
            style={[styles.placeOrderButton, (!selectedAddressId || placeOrder.isPending) && styles.placeOrderButtonDisabled]}
            onPress={handlePlaceOrder}
            disabled={!selectedAddressId || placeOrder.isPending}
          >
            <Text variant="button" color={colors.textOnAccent}>
              {placeOrder.isPending ? "Placing order..." : "Place Order"}
            </Text>
            <Feather name="arrow-right" size={16} color={colors.textOnAccent} />
          </Pressable>
        </View>
      </View>
    </Screen>
  );
}

function PaymentOption({
  label,
  description,
  icon,
  selected,
  onPress,
}: {
  label: string;
  description: string;
  icon: keyof typeof Feather.glyphMap;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      style={[styles.paymentOption, selected && styles.paymentOptionSelected]}
      onPress={onPress}
      accessibilityRole="radio"
      accessibilityState={{ selected }}
    >
      <View style={styles.paymentIcon}>
        <Feather name={icon} size={18} color={selected ? colors.primary : colors.textSecondary} />
      </View>
      <View style={{ flex: 1 }}>
        <Text variant="bodyMedium">{label}</Text>
        <Text variant="caption" color={colors.textSecondary}>
          {description}
        </Text>
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
    paddingBottom: spacing.xs,
  },
  headerRight: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  headerLogo: { width: 24, height: 24 * (1149 / 1369), borderRadius: 0 },
  trustStrip: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.base,
    paddingBottom: spacing.sm,
  },
  trustItem: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
  trustPill: { backgroundColor: colors.accentLight, borderRadius: radius.none, paddingHorizontal: spacing.xs, paddingVertical: 3 },
  content: { padding: spacing.base, paddingBottom: spacing["3xl"] },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  errorTitle: { marginTop: spacing.lg },
  errorMessage: { marginTop: spacing.sm },
  addressOption: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm, marginBottom: spacing.md },
  addressTitleRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
  primaryBadge: { backgroundColor: colors.primaryLight, borderRadius: radius.none, paddingHorizontal: 4, paddingVertical: 1 },
  addAddressLink: { flexDirection: "row", alignItems: "center", marginTop: spacing.xs },
  radio: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
  },
  radioActive: { borderColor: colors.primary },
  radioDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.primary },
  paymentOption: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.none,
    borderWidth: 1.5,
    borderColor: colors.border,
    marginBottom: spacing.sm,
  },
  paymentOptionSelected: { borderColor: colors.primary, backgroundColor: colors.primaryLight },
  paymentIcon: { width: 32, alignItems: "center" },
  promoRow: { flexDirection: "row", gap: spacing.sm },
  promoInputWrapper: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    borderWidth: 1.5,
    borderColor: colors.border,
    borderRadius: radius.none,
    paddingHorizontal: spacing.sm,
  },
  promoInput: { flex: 1, paddingVertical: spacing.sm, fontSize: 14, color: colors.textPrimary },
  promoApplyButton: {
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.accent,
    borderRadius: radius.none,
    paddingHorizontal: spacing.lg,
  },
  promoAppliedRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.sm,
    borderWidth: 1.5,
    borderColor: colors.success,
    backgroundColor: colors.primaryLight,
    borderRadius: radius.none,
  },
  discountSummaryRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.sm,
  },
  sustainabilityNote: { marginTop: spacing.sm, marginBottom: spacing.base },
  footer: { padding: spacing.base, paddingTop: spacing.sm, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.surface },
  footerNote: { textAlign: "center", marginBottom: spacing.sm },
  placeOrderBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: colors.primary,
    borderRadius: radius.none,
    paddingHorizontal: spacing.base,
    height: 56,
  },
  placeOrderButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.accent,
    borderRadius: radius.none,
    paddingHorizontal: spacing.lg,
    height: 44,
  },
  placeOrderButtonDisabled: { opacity: 0.5 },
});
