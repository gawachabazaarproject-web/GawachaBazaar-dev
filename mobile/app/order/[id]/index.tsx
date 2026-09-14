import React from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { StatusBadge } from "@/components/StatusBadge";
import { OrderTimeline } from "@/features/orders/OrderTimeline";
import { useOrder, useOrderFulfillment, useOrderPayment, useOrderRefund } from "@/features/orders/useOrders";
import { presentOrderStatus, presentPaymentStatus, isOrderCancellable } from "@/utils/statusPresentation";
import { formatMoney } from "@/utils/money";
import { colors, radius, spacing } from "@/theme";

export default function OrderDetailsScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const orderId = Number(id);
  const router = useRouter();

  const { data: order, isLoading } = useOrder(orderId);
  const { data: fulfillment } = useOrderFulfillment(orderId);
  const { data: payment } = useOrderPayment(orderId);
  const { data: refund } = useOrderRefund(orderId);

  if (isLoading || !order) {
    return (
      <Screen>
        <Stack.Screen options={{ headerShown: true, title: "Order" }} />
        <View style={styles.centered}>
          <ActivityIndicator color={colors.primary} />
        </View>
      </Screen>
    );
  }

  const orderPresentation = presentOrderStatus(order.status);
  const cancellable = isOrderCancellable(order.status);

  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: `Order ${order.order_number}` }} />
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.headerRow}>
          <View>
            <Text variant="h2">Order {order.order_number}</Text>
            <Text variant="bodySmall" color={colors.textSecondary}>
              Placed {new Date(order.placed_at).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}
            </Text>
          </View>
          <StatusBadge presentation={orderPresentation} />
        </View>

        <SectionCard title="Status">
          <OrderTimeline orderStatus={order.status} fulfillmentStatus={fulfillment?.status ?? null} />
        </SectionCard>

        <SectionCard title={`Items (${order.items.length})`}>
          {order.items.map((item) => (
            <View key={item.id} style={styles.itemRow}>
              <View style={{ flex: 1 }}>
                <Text variant="body" numberOfLines={1}>
                  {item.product_name}
                </Text>
                <Text variant="caption" color={colors.textSecondary}>
                  {item.variant_name} x {Math.round(Number.parseFloat(item.quantity))}
                </Text>
              </View>
              <Text variant="bodyMedium">{formatMoney(item.total_price, order.currency)}</Text>
            </View>
          ))}
          <View style={styles.divider} />
          <View style={styles.itemRow}>
            <Text variant="h3">Total</Text>
            <Text variant="h3">{formatMoney(order.total_amount, order.currency)}</Text>
          </View>
        </SectionCard>

        {order.address ? (
          <SectionCard title="Delivery address">
            <Text variant="body">
              {order.address.address_line_1}
              {order.address.address_line_2 ? `, ${order.address.address_line_2}` : ""}
            </Text>
            <Text variant="body" color={colors.textSecondary}>
              {order.address.city}, {order.address.state} {order.address.postal_code}
            </Text>
          </SectionCard>
        ) : null}

        {payment ? (
          <SectionCard title="Payment">
            <View style={styles.itemRow}>
              <Text variant="body" color={colors.textSecondary}>
                Method
              </Text>
              <Text variant="bodyMedium">{payment.payment_method === "COD" ? "Cash on Delivery" : "UPI"}</Text>
            </View>
            <View style={[styles.itemRow, { marginTop: spacing.sm }]}>
              <Text variant="body" color={colors.textSecondary}>
                Status
              </Text>
              <StatusBadge presentation={presentPaymentStatus(payment.status)} />
            </View>
          </SectionCard>
        ) : null}

        {order.cancellation_reason ? (
          <SectionCard title="Cancellation">
            <Text variant="body" color={colors.textSecondary}>
              {order.cancellation_reason}
            </Text>
          </SectionCard>
        ) : null}

        {refund ? (
          <Pressable onPress={() => router.push(`/order/${orderId}/refund`)}>
            <SectionCard title="Refund">
              <View style={styles.itemRow}>
                <Text variant="body" color={colors.textSecondary}>
                  View refund status
                </Text>
                <Feather name="chevron-right" size={18} color={colors.textMuted} />
              </View>
            </SectionCard>
          </Pressable>
        ) : null}

        {cancellable ? (
          <Button
            label="Cancel order"
            variant="outline"
            onPress={() => router.push(`/order/${orderId}/cancel`)}
            style={{ marginTop: spacing.sm }}
          />
        ) : null}
      </ScrollView>
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

const styles = StyleSheet.create({
  content: { padding: spacing.base, paddingBottom: spacing["3xl"] },
  centered: { flex: 1, alignItems: "center", justifyContent: "center" },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: spacing.lg },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.divider,
    borderRadius: radius.none,
    padding: spacing.base,
    marginBottom: spacing.base,
  },
  cardTitle: { marginBottom: spacing.md },
  itemRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: spacing.xs, marginBottom: spacing.xs },
  divider: { height: 1, backgroundColor: colors.divider, marginVertical: spacing.sm },
});
