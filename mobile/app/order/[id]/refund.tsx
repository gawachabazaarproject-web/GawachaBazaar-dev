import React from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { Stack, useLocalSearchParams } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { useOrderRefund } from "@/features/orders/useOrders";
import { presentRefundStatus } from "@/utils/statusPresentation";
import { formatMoney } from "@/utils/money";
import { colors, radius, spacing } from "@/theme";
import { RefundStatus } from "@/types/api";

const TIMELINE: { key: RefundStatus; label: string }[] = [
  { key: "PENDING_APPROVAL", label: "Refund requested" },
  { key: "APPROVED", label: "Approved by GawachaBazaar" },
  { key: "PROCESSING", label: "Processing with bank" },
  { key: "REFUNDED", label: "Refunded" },
];

/**
 * Refund status (brief §34/Phase 18): reflects exactly what
 * GET /orders/{id}/refund returns - this screen never implies money has
 * moved before the backend says REFUNDED, and never lets a customer
 * approve/trigger their own refund (that's ADMIN-only, enforced
 * server-side - this screen has no such action at all).
 */
export default function RefundStatusScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data: refund, isLoading, isError } = useOrderRefund(Number(id));

  if (isLoading) {
    return (
      <Screen>
        <Stack.Screen options={{ headerShown: true, title: "Refund status" }} />
        <View style={styles.centered}>
          <ActivityIndicator color={colors.primary} />
        </View>
      </Screen>
    );
  }

  if (isError || !refund) {
    return (
      <Screen>
        <Stack.Screen options={{ headerShown: true, title: "Refund status" }} />
        <EmptyState icon="info" title="No refund on this order" message="This order doesn't have a refund associated with it." />
      </Screen>
    );
  }

  const presentation = presentRefundStatus(refund.status);
  const isTerminalNegative = refund.status === "REJECTED" || refund.status === "FAILED";
  const activeIndex = TIMELINE.findIndex((t) => t.key === refund.status);

  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: "Refund status" }} />
      <View style={styles.content}>
        <View style={styles.summaryCard}>
          <Text variant="caption" color={colors.textSecondary}>
            Refund amount
          </Text>
          <Text variant="priceLarge" color={colors.price}>
            {formatMoney(refund.amount, refund.currency)}
          </Text>
          <View style={{ marginTop: spacing.sm }}>
            <StatusBadge presentation={presentation} />
          </View>
        </View>

        {isTerminalNegative ? (
          <View style={styles.negativeBanner}>
            <Feather name="alert-circle" size={20} color={colors.error} />
            <Text variant="body" color={colors.error} style={{ marginLeft: spacing.sm, flex: 1 }}>
              {refund.status === "REJECTED"
                ? "This refund request was rejected. Contact support if you have questions."
                : "This refund attempt failed. Our team has been notified and will retry it."}
            </Text>
          </View>
        ) : (
          <View style={styles.timeline}>
            {TIMELINE.map((step, idx) => (
              <View key={step.key} style={styles.timelineRow}>
                <View style={[styles.dot, idx <= activeIndex && styles.dotDone]}>
                  {idx <= activeIndex ? <Feather name="check" size={11} color={colors.textInverse} /> : null}
                </View>
                <Text variant="body" color={idx <= activeIndex ? colors.textPrimary : colors.textMuted} style={styles.timelineLabel}>
                  {step.label}
                </Text>
              </View>
            ))}
          </View>
        )}

        <Text variant="caption" color={colors.textMuted} style={styles.note}>
          Requested on {new Date(refund.requested_at).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}
        </Text>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  centered: { flex: 1, alignItems: "center", justifyContent: "center" },
  content: { padding: spacing.base },
  summaryCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.none,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    alignItems: "center",
    marginBottom: spacing.xl,
  },
  negativeBanner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.errorLight,
    borderRadius: radius.none,
    padding: spacing.base,
  },
  timeline: { paddingLeft: spacing.sm },
  timelineRow: { flexDirection: "row", alignItems: "center", marginBottom: spacing.lg },
  dot: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
  },
  dotDone: { backgroundColor: colors.success, borderColor: colors.success },
  timelineLabel: { marginLeft: spacing.md },
  note: { marginTop: spacing.base, textAlign: "center" },
});
