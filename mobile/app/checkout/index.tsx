import React, { useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Stack, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { useCart } from "@/features/cart/useCart";
import { useAddresses } from "@/features/address/useAddresses";
import { usePlaceOrder, PlaceOrderResult } from "@/features/checkout/useCheckout";
import { useCancelOrder } from "@/features/orders/useOrders";
import { formatMoney } from "@/utils/money";
import { colors, radius, spacing } from "@/theme";
import { PaymentMethod } from "@/types/api";

export default function CheckoutScreen() {
  const router = useRouter();
  const { data: cart } = useCart();
  const { data: addresses } = useAddresses();
  const placeOrder = usePlaceOrder();
  const cancelOrder = useCancelOrder();

  const [selectedAddressId, setSelectedAddressId] = useState<number | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("COD");
  const [result, setResult] = useState<PlaceOrderResult | null>(null);

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
      { addressId: selectedAddressId, paymentMethod },
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

  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: "Checkout" }} />
      <ScrollView contentContainerStyle={styles.content}>
        {/* Delivery address */}
        <SectionCard title="Delivery address">
          {(addresses ?? []).map((address) => (
            <Pressable
              key={address.id}
              style={styles.addressOption}
              onPress={() => setSelectedAddressId(address.id)}
            >
              <View style={[styles.radio, selectedAddressId === address.id && styles.radioActive]}>
                {selectedAddressId === address.id ? <View style={styles.radioDot} /> : null}
              </View>
              <View style={{ flex: 1 }}>
                <Text variant="bodyMedium">{address.label}</Text>
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
        </SectionCard>

        {/* Order items */}
        <SectionCard title={`Order items (${cart.items.length})`}>
          {cart.items.map((item) => (
            <View key={item.id} style={styles.itemRow}>
              <Text variant="body" style={{ flex: 1 }} numberOfLines={1}>
                {item.product_name} <Text variant="caption" color={colors.textSecondary}>x{Math.round(Number.parseFloat(item.quantity))}</Text>
              </Text>
              <Text variant="bodyMedium">{item.line_total ? formatMoney(item.line_total, item.currency ?? "INR") : "-"}</Text>
            </View>
          ))}
        </SectionCard>

        {/* Payment method */}
        <SectionCard title="Payment method">
          <PaymentOption
            label="Cash on Delivery"
            description="Pay in cash when your order arrives"
            icon="dollar-sign"
            selected={paymentMethod === "COD"}
            onPress={() => setPaymentMethod("COD")}
          />
          <PaymentOption
            label="UPI"
            description="Pay online via UPI"
            icon="smartphone"
            selected={paymentMethod === "UPI"}
            onPress={() => setPaymentMethod("UPI")}
          />
        </SectionCard>

        {/* Price summary */}
        <SectionCard title="Price summary">
          <View style={styles.summaryRow}>
            <Text variant="body" color={colors.textSecondary}>
              Subtotal
            </Text>
            <Text variant="body">{formatMoney(cart.total_amount ?? "0", cart.currency ?? "INR")}</Text>
          </View>
          <View style={[styles.summaryRow, { marginTop: spacing.sm }]}>
            <Text variant="h3">Total</Text>
            <Text variant="h3">{formatMoney(cart.total_amount ?? "0", cart.currency ?? "INR")}</Text>
          </View>
        </SectionCard>
      </ScrollView>

      <View style={styles.footer}>
        {paymentMethod === "COD" ? (
          <Text variant="caption" color={colors.textSecondary} style={styles.footerNote}>
            Amount to pay on delivery: {formatMoney(cart.total_amount ?? "0", cart.currency ?? "INR")}
          </Text>
        ) : null}
        <Button
          label={placeOrder.isPending ? "Placing order..." : "Place order"}
          onPress={handlePlaceOrder}
          loading={placeOrder.isPending}
          disabled={!selectedAddressId}
          fullWidth
          size="lg"
        />
      </View>
    </Screen>
  );
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.card}>
      <Text variant="h3" style={styles.cardTitle}>
        {title}
      </Text>
      {children}
    </View>
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
    <Pressable style={[styles.paymentOption, selected && styles.paymentOptionSelected]} onPress={onPress}>
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
  content: { padding: spacing.base, paddingBottom: spacing["3xl"] },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  errorTitle: { marginTop: spacing.lg },
  errorMessage: { marginTop: spacing.sm },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.base,
    marginBottom: spacing.base,
  },
  cardTitle: { marginBottom: spacing.md },
  addressOption: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm, marginBottom: spacing.md },
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
  itemRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: spacing.sm },
  paymentOption: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1.5,
    borderColor: colors.border,
    marginBottom: spacing.sm,
  },
  paymentOptionSelected: { borderColor: colors.primary, backgroundColor: colors.primaryLight },
  paymentIcon: { width: 32, alignItems: "center" },
  summaryRow: { flexDirection: "row", justifyContent: "space-between" },
  footer: { padding: spacing.base, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.surface },
  footerNote: { textAlign: "center", marginBottom: spacing.sm },
});
