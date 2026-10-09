import React, { useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { useQueryClient } from "@tanstack/react-query";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { OrderProgress, buildProgressSteps } from "@/features/orders/OrderProgress";
import { useOrder, useOrderFulfillment, useOrderPayment, useOrderRefund } from "@/features/orders/useOrders";
import { cartQueryKey } from "@/features/cart/useCart";
import { useOnlinePayment } from "@/features/payment/useOnlinePayment";
import { RazorpayCheckout } from "@/components/payment/RazorpayCheckout";
import { cartApi } from "@/api";
import { useToastStore } from "@/store/toastStore";
import { presentPaymentStatus, isOrderCancellable } from "@/utils/statusPresentation";
import { formatMoney } from "@/utils/money";
import { colors, radius, spacing } from "@/theme";
import { FulfillmentStatus, OrderStatus } from "@/types/api";

const TINT = colors.surfaceTint; // pale sage wash used by the hero, total box and pills

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", hour12: true }).toUpperCase();

interface Hero {
  icon: keyof typeof Feather.glyphMap;
  pillIcon: keyof typeof Feather.glyphMap;
  pill: string;
  title: string;
  subtitle: string;
  tone: string;
}

// Little sparkle dashes around the status circle.
const TICK_RADIUS = 31;
const TICKS = [{ deg: -50 }, { deg: -10 }, { deg: 35 }, { deg: 150 }, { deg: 215 }];

function heroFor(status: OrderStatus, fulfillment: FulfillmentStatus | null): Hero {
  const delivered = status === "COMPLETED" || fulfillment === "DELIVERED";
  if (delivered)
    return {
      icon: "check", pillIcon: "truck", pill: "Delivered", tone: colors.brandGreen,
      title: "Delivered successfully", subtitle: "Your fresh items have been delivered.",
    };
  if (status === "CANCELLED")
    return {
      icon: "x", pillIcon: "x-circle", pill: "Cancelled", tone: colors.error,
      title: "Order cancelled", subtitle: "This order was cancelled.",
    };
  if (status === "EXPIRED")
    return {
      icon: "clock", pillIcon: "clock", pill: "Expired", tone: colors.textMuted,
      title: "Order expired", subtitle: "Payment was not completed in time.",
    };
  if (status === "PENDING")
    return {
      icon: "clock", pillIcon: "credit-card", pill: "Payment pending", tone: colors.warning,
      title: "Awaiting payment", subtitle: "Complete payment to confirm your order.",
    };
  if (fulfillment === "OUT_FOR_DELIVERY")
    return {
      icon: "truck", pillIcon: "truck", pill: "Out for delivery", tone: colors.brandGreen,
      title: "On its way", subtitle: "Your order is out for delivery.",
    };
  return {
    icon: "package", pillIcon: "package", pill: "Confirmed", tone: colors.brandGreen,
    title: "Preparing your order", subtitle: "We are packing your fresh items.",
  };
}

export default function OrderDetailsScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const orderId = Number(id);
  const router = useRouter();
  const queryClient = useQueryClient();
  const showToast = useToastStore((s) => s.show);
  const [reordering, setReordering] = useState(false);

  const { data: order, isLoading } = useOrder(orderId);
  const { data: fulfillment } = useOrderFulfillment(orderId);
  const { data: payment } = useOrderPayment(orderId);
  const { data: refund } = useOrderRefund(orderId);
  const online = useOnlinePayment();

  if (isLoading || !order) {
    return (
      <Screen>
        <Stack.Screen options={{ headerShown: false }} />
        <View style={styles.centered}>
          <ActivityIndicator color={colors.primary} />
        </View>
      </Screen>
    );
  }

  const cancellable = isOrderCancellable(order.status);
  const hero = heroFor(order.status, fulfillment?.status ?? null);
  const deliveredAt = fulfillment?.delivered_at ?? null;
  const showSteps = order.status !== "CANCELLED" && order.status !== "EXPIRED";
  const steps = buildProgressSteps(order.status, fulfillment?.status ?? null, {
    placed: fmtTime(order.placed_at),
    delivered: deliveredAt ? fmtTime(deliveredAt) : null,
  });
  const delivery = Number.parseFloat(order.delivery_fee ?? "0");
  const discount = Number.parseFloat(order.discount_amount ?? "0");

  const getHelp = () => router.push("/account/support");

  const openMenu = () => {
    const buttons = [
      { text: "Get help", onPress: getHelp },
      ...(refund ? [{ text: "View refund", onPress: () => router.push(`/order/${orderId}/refund`) }] : []),
      ...(cancellable
        ? [{ text: "Cancel order", style: "destructive" as const, onPress: () => router.push(`/order/${orderId}/cancel`) }]
        : []),
      { text: "Close", style: "cancel" as const },
    ];
    Alert.alert(`Order ${order.order_number}`, undefined, buttons);
  };

  const reorder = async () => {
    setReordering(true);
    let added = 0;
    for (const item of order.items) {
      try {
        await cartApi.addItem(item.variant_id, item.quantity);
        added += 1;
      } catch {
        // Item may be unavailable now - skip it and add the rest.
      }
    }
    await queryClient.invalidateQueries({ queryKey: cartQueryKey });
    setReordering(false);
    if (added === 0) {
      showToast("Those items are not available right now.", "error");
      return;
    }
    if (added < order.items.length) showToast("Some items are no longer available.");
    router.push("/cart");
  };

  const paymentTitle =
    payment?.payment_method === "COD"
      ? "Cash on delivery"
      : payment?.status === "PAID"
        ? "Paid online"
        : "Online payment";

  return (
    <Screen>
      <Stack.Screen options={{ headerShown: false }} />
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} hitSlop={10} accessibilityRole="button" accessibilityLabel="Go back">
            <Feather name="arrow-left" size={24} color={colors.textPrimary} />
          </Pressable>
          <View style={styles.headerText}>
            <Text variant="displayM" color={colors.primary} style={styles.headerTitle}>
              Order details
            </Text>
            <Text variant="bodySmall" color={colors.textSecondary} numberOfLines={1}>
              {order.order_number}
            </Text>
          </View>
          <Pressable onPress={openMenu} hitSlop={10} accessibilityRole="button" accessibilityLabel="More options">
            <Feather name="more-vertical" size={22} color={colors.textPrimary} />
          </Pressable>
        </View>

        {/* Status hero */}
        <View style={styles.hero}>
          <Image
            source={require("../../../assets/order-hero-crate.png")}
            style={styles.heroArt}
            contentFit="contain"
            pointerEvents="none"
          />
          <View style={styles.heroTop}>
            <View style={[styles.checkRing, { backgroundColor: `${hero.tone}33` }]}>
              {TICKS.map((t, i) => (
                <View
                  key={i}
                  style={[styles.tick, { backgroundColor: hero.tone, transform: [{ rotate: `${t.deg}deg` }, { translateY: -TICK_RADIUS }], opacity: 0.55 }]}
                />
              ))}
              <View style={[styles.checkCircle, { backgroundColor: hero.tone }]}>
                <Feather name={hero.icon} size={26} color={colors.textInverse} />
              </View>
            </View>
            <View style={styles.heroText}>
              <View style={[styles.pill, { backgroundColor: `${hero.tone}1F` }]}>
                <Feather name={hero.pillIcon} size={13} color={hero.tone} />
                <Text variant="titleSmall" color={colors.primary} style={{ fontSize: 11.5 }}>
                  {hero.pill}
                </Text>
              </View>
              <Text variant="displayM" color={colors.primary} style={styles.heroTitle}>
                {hero.title}
              </Text>
              <Text variant="caption" color={colors.textSecondary} style={{ fontSize: 11 }}>
                {hero.subtitle}
              </Text>
            </View>
          </View>
          <View style={styles.heroMeta}>
            <View style={styles.metaItem}>
              <Feather name="calendar" size={15} color={colors.textSecondary} />
              <Text variant="caption" color={colors.textPrimary} style={{ fontSize: 11 }}>
                {fmtDate(deliveredAt && hero.pill === "Delivered" ? deliveredAt : order.placed_at)}
              </Text>
            </View>
            <View style={styles.metaDivider} />
            <View style={styles.metaItem}>
              <Feather name="clock" size={15} color={colors.textSecondary} />
              <Text variant="caption" color={colors.textPrimary} style={{ fontSize: 11 }}>
                {deliveredAt && hero.pill === "Delivered"
                  ? `Delivered at ${fmtTime(deliveredAt)}`
                  : `Placed at ${fmtTime(order.placed_at)}`}
              </Text>
            </View>
          </View>
        </View>

        {/* Progress */}
        {showSteps ? (
          <View style={styles.card}>
            <OrderProgress steps={steps} />
          </View>
        ) : null}

        {/* Items */}
        <View style={styles.card}>
          <View style={styles.itemsHeader}>
            <Text variant="displayM" color={colors.primary} style={styles.itemsTitle}>
              Items ({order.items.length})
            </Text>
            <View style={styles.farmPill}>
              <Feather name="shopping-bag" size={14} color={colors.primary} />
              <Text variant="captionMedium" color={colors.primary} style={styles.farmPillText}>
                Fresh from local farms
              </Text>
            </View>
          </View>

          {order.items.map((item, i) => (
            <View key={item.id} style={[styles.itemRow, i === order.items.length - 1 && styles.itemRowLast]}>
              <View style={styles.thumb}>
                {item.image_url ? (
                  <Image source={item.image_url} style={styles.thumbImage} contentFit="cover" transition={150} />
                ) : (
                  <Feather name="package" size={18} color={colors.textMuted} />
                )}
              </View>
              <View style={styles.itemText}>
                <Text variant="body" color={colors.textPrimary} numberOfLines={1} style={styles.itemName}>
                  {item.product_name}
                </Text>
                <Text variant="caption" color={colors.textSecondary} style={{ fontSize: 10.5 }}>
                  {item.variant_name} x {Math.round(Number.parseFloat(item.quantity))}
                </Text>
              </View>
              <Text variant="bodyMedium" color={colors.price} style={{ fontSize: 13 }}>
                {formatMoney(item.total_price, order.currency)}
              </Text>
            </View>
          ))}

          {delivery > 0 || discount > 0 ? (
            <View style={styles.breakdown}>
              {discount > 0 ? (
                <View style={styles.breakdownRow}>
                  <Text variant="bodySmall" color={colors.textSecondary}>
                    Discount
                  </Text>
                  <Text variant="bodySmall" color={colors.discount}>
                    -{formatMoney(order.discount_amount, order.currency)}
                  </Text>
                </View>
              ) : null}
              {delivery > 0 ? (
                <View style={styles.breakdownRow}>
                  <Text variant="bodySmall" color={colors.textSecondary}>
                    Delivery fee
                  </Text>
                  <Text variant="bodySmall" color={colors.textPrimary}>
                    {formatMoney(order.delivery_fee, order.currency)}
                  </Text>
                </View>
              ) : null}
            </View>
          ) : null}

          <View style={styles.totalBox}>
            <Text variant="displayM" color={colors.primary} style={styles.totalLabel}>
              Total
            </Text>
            <Text variant="price" color={colors.primary} style={{ fontSize: 19 }}>
              {formatMoney(order.total_amount, order.currency)}
            </Text>
          </View>
        </View>

        {/* Payment */}
        {payment ? (
          <View style={styles.card}>
            <Text variant="displayM" color={colors.primary} style={styles.sectionTitle}>
              Payment details
            </Text>
            <View style={styles.payRow}>
              <View style={styles.walletCircle}>
                <Feather name="briefcase" size={18} color={colors.primary} />
              </View>
              <View style={styles.payText}>
                <Text variant="body" color={colors.textPrimary} style={{ fontSize: 13 }}>
                  {paymentTitle}
                </Text>
                <Text variant="caption" color={colors.textSecondary} style={{ fontSize: 10.5 }}>
                  {fmtDate(payment.paid_at ?? payment.created_at)}, {fmtTime(payment.paid_at ?? payment.created_at)}
                </Text>
              </View>
              <View style={styles.payRight}>
                <Text variant="bodyMedium" color={colors.price} style={{ fontSize: 14 }}>
                  {formatMoney(payment.amount, payment.currency)}
                </Text>
                <View style={[styles.statusPill, { backgroundColor: presentPaymentStatus(payment.status).backgroundColor }]}>
                  {payment.status === "PAID" ? (
                    <Feather name="check-circle" size={12} color={colors.success} />
                  ) : null}
                  <Text variant="captionMedium" color={presentPaymentStatus(payment.status).color} style={{ fontSize: 10.5 }}>
                    {presentPaymentStatus(payment.status).label}
                  </Text>
                </View>
              </View>
            </View>

            {payment.payment_method === "UPI" &&
            order.status === "PENDING" &&
            ["PROCESSING", "FAILED", "EXPIRED"].includes(payment.status) ? (
              <>
                {online.error ? (
                  <Text variant="bodySmall" color={colors.error} style={{ marginTop: spacing.sm }}>
                    {online.error}
                  </Text>
                ) : null}
                <Button
                  label={`${payment.status === "PROCESSING" ? "Complete payment" : "Try paying again"} · ${formatMoney(payment.amount, payment.currency)}`}
                  onPress={() => online.retryForOrder(orderId)}
                  loading={online.busy}
                  fullWidth
                  style={{ marginTop: spacing.md }}
                />
              </>
            ) : null}
          </View>
        ) : null}

        <RazorpayCheckout
          checkout={online.checkout}
          onSuccess={(response) => online.complete(response)}
          onDismiss={online.dismiss}
        />

        {order.address ? (
          <View style={styles.card}>
            <Text variant="displayM" color={colors.primary} style={styles.sectionTitle}>
              Delivery address
            </Text>
            <Text variant="bodySmall" color={colors.textPrimary} style={{ marginTop: spacing.xs }}>
              {order.address.address_line_1}
              {order.address.address_line_2 ? `, ${order.address.address_line_2}` : ""}
            </Text>
            <Text variant="bodySmall" color={colors.textSecondary}>
              {order.address.city}, {order.address.state} {order.address.postal_code}
            </Text>
          </View>
        ) : null}

        {order.cancellation_reason ? (
          <View style={styles.card}>
            <Text variant="displayM" color={colors.primary} style={styles.sectionTitle}>
              Cancellation
            </Text>
            <Text variant="body" color={colors.textSecondary}>
              {order.cancellation_reason}
            </Text>
          </View>
        ) : null}

        {refund ? (
          <Pressable style={styles.card} onPress={() => router.push(`/order/${orderId}/refund`)}>
            <View style={styles.refundRow}>
              <Text variant="bodyLarge" color={colors.textPrimary}>
                View refund status
              </Text>
              <Feather name="chevron-right" size={18} color={colors.textMuted} />
            </View>
          </Pressable>
        ) : null}

        {/* Actions */}
        <View style={styles.actions}>
          <Pressable
            onPress={reorder}
            disabled={reordering}
            style={[styles.reorderBtn, reordering && { opacity: 0.6 }]}
            accessibilityRole="button"
            accessibilityLabel="Reorder"
          >
            {reordering ? (
              <ActivityIndicator color={colors.textInverse} />
            ) : (
              <>
                <Feather name="refresh-cw" size={18} color={colors.textInverse} />
                <Text variant="h3" color={colors.textInverse} style={{ fontSize: 16 }}>
                  Reorder
                </Text>
              </>
            )}
          </Pressable>
          <Pressable onPress={getHelp} style={styles.helpBtn} accessibilityRole="button" accessibilityLabel="Get help">
            <Feather name="headphones" size={18} color={colors.primary} />
            <Text variant="h3" color={colors.primary} style={{ fontSize: 16 }}>
              Get help
            </Text>
          </Pressable>
        </View>

        {cancellable ? (
          <Pressable onPress={() => router.push(`/order/${orderId}/cancel`)} style={styles.cancelLink} accessibilityRole="button">
            <Text variant="bodyMedium" color={colors.error}>
              Cancel order
            </Text>
          </Pressable>
        ) : null}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: spacing.base, paddingBottom: spacing["3xl"] },
  centered: { flex: 1, alignItems: "center", justifyContent: "center" },

  header: { flexDirection: "row", alignItems: "center", gap: spacing.base, paddingVertical: spacing.md },
  headerText: { flex: 1 },
  headerTitle: { fontSize: 18, lineHeight: 23 },

  hero: {
    backgroundColor: TINT,
    borderRadius: 18,
    padding: spacing.md,
    marginTop: 44,
  },
  heroArt: { position: "absolute", right: -18, bottom: 0, width: 128, height: 164 },
  tick: { position: "absolute", width: 2.5, height: 7, borderRadius: 2 },
  heroTop: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  checkRing: { width: 68, height: 68, borderRadius: 34, alignItems: "center", justifyContent: "center" },
  checkCircle: { width: 50, height: 50, borderRadius: 25, alignItems: "center", justifyContent: "center" },
  heroText: { flex: 1, alignItems: "flex-start", marginRight: 70 },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  heroTitle: { marginTop: spacing.xs, fontSize: 17.5, lineHeight: 22 },
  heroMeta: { flexDirection: "row", alignItems: "center", marginTop: spacing.md },
  metaItem: { flexDirection: "row", alignItems: "center", gap: 6, flexShrink: 1 },
  metaDivider: { width: 1, height: 20, backgroundColor: colors.borderStrong, marginHorizontal: spacing.md },

  card: {
    backgroundColor: colors.surface,
    borderRadius: 18,
    padding: spacing.md,
    marginTop: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  sectionTitle: { fontSize: 15, lineHeight: 20 },
  itemsTitle: { fontSize: 17.5, lineHeight: 22 },

  itemsHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.md },
  farmPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: TINT,
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  farmPillText: { fontSize: 10.5 },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
    gap: spacing.md,
  },
  itemRowLast: { borderBottomWidth: 0 },
  thumb: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  thumbImage: { width: "100%", height: "100%" },
  itemText: { flex: 1 },
  itemName: { fontFamily: "PlusJakartaSans_600SemiBold", fontSize: 12.5, lineHeight: 17 },

  breakdown: { marginTop: spacing.xs, gap: spacing.xs, paddingHorizontal: spacing.sm },
  breakdownRow: { flexDirection: "row", justifyContent: "space-between" },
  totalBox: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: TINT,
    borderRadius: 14,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginTop: spacing.sm,
  },
  totalLabel: { fontSize: 17.5, lineHeight: 22 },

  payRow: { flexDirection: "row", alignItems: "center", marginTop: spacing.sm, gap: spacing.md },
  walletCircle: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: TINT,
    alignItems: "center",
    justifyContent: "center",
  },
  payText: { flex: 1 },
  payRight: { alignItems: "flex-end", gap: 6 },
  statusPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },

  refundRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },

  actions: { flexDirection: "row", gap: spacing.md, marginTop: spacing.lg },
  reorderBtn: {
    flex: 1,
    height: 44,
    borderRadius: 12,
    backgroundColor: colors.primary,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
  },
  helpBtn: {
    flex: 1,
    height: 44,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.surface,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
  },
  cancelLink: { alignSelf: "center", paddingVertical: spacing.base, marginTop: spacing.xs },
});
