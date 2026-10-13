import React from "react";
import { StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { colors, spacing } from "@/theme";
import { FulfillmentStatus, OrderStatus } from "@/types/api";

const FULFILLMENT_ORDER: FulfillmentStatus[] = [
  "PENDING",
  "PICKING",
  "PACKED",
  "READY_FOR_DELIVERY",
  "ASSIGNED",
  "OUT_FOR_DELIVERY",
  "DELIVERED",
];

export interface ProgressStep {
  key: string;
  label: string;
  done: boolean;
  /** Pre-formatted time, shown only when the backend actually recorded it. */
  time?: string | null;
}

/** The five milestones, derived only from real Order/Fulfillment statuses. */
export function buildProgressSteps(
  orderStatus: OrderStatus,
  fulfillmentStatus: FulfillmentStatus | null,
  times: { placed?: string | null; delivered?: string | null },
): ProgressStep[] {
  const idx = fulfillmentStatus ? FULFILLMENT_ORDER.indexOf(fulfillmentStatus) : -1;
  const confirmed = orderStatus === "CONFIRMED" || orderStatus === "COMPLETED";
  const delivered = idx >= 6 || orderStatus === "COMPLETED";
  return [
    { key: "placed", label: "Order placed", done: true, time: times.placed },
    { key: "confirmed", label: "Confirmed", done: confirmed },
    { key: "preparing", label: "Preparing your order", done: confirmed && idx >= 1 },
    { key: "out", label: "Out for delivery", done: idx >= 5 },
    { key: "delivered", label: "Delivered", done: delivered, time: delivered ? times.delivered : null },
  ];
}

/** Horizontal five-step tracker: green check circles joined by a line,
 * label under each, time under the label when known. */
export function OrderProgress({ steps }: { steps: ProgressStep[] }) {
  const current = steps.reduce((acc, s, i) => (s.done ? i : acc), 0);
  return (
    <View style={styles.row}>
      {steps.map((step, i) => (
        <View key={step.key} style={styles.step}>
          <View style={styles.circleRow}>
            <View style={[styles.connector, i === 0 && styles.hidden, steps[i].done && styles.connectorDone]} />
            <View style={[styles.circle, step.done ? styles.circleDone : styles.circlePending]}>
              {step.done ? <Feather name="check" size={12} color={colors.textInverse} /> : null}
            </View>
            <View
              style={[
                styles.connector,
                i === steps.length - 1 && styles.hidden,
                steps[i + 1]?.done && styles.connectorDone,
              ]}
            />
          </View>
          <Text
            variant="caption"
            color={step.done ? colors.textPrimary : colors.textMuted}
            align="center"
            style={[styles.label, i === current && styles.labelCurrent]}
          >
            {step.label}
          </Text>
          {step.time ? (
            <Text variant="caption" color={colors.textMuted} align="center" style={styles.time}>
              {step.time}
            </Text>
          ) : null}
        </View>
      ))}
    </View>
  );
}

const CIRCLE = 22;

const styles = StyleSheet.create({
  row: { flexDirection: "row" },
  step: { flex: 1, alignItems: "center" },
  circleRow: { flexDirection: "row", alignItems: "center", alignSelf: "stretch" },
  connector: { flex: 1, height: 2, backgroundColor: colors.border },
  connectorDone: { backgroundColor: colors.brandGreen },
  hidden: { opacity: 0 },
  circle: {
    width: CIRCLE,
    height: CIRCLE,
    borderRadius: CIRCLE / 2,
    alignItems: "center",
    justifyContent: "center",
  },
  circleDone: { backgroundColor: colors.brandGreen },
  circlePending: { backgroundColor: colors.surface, borderWidth: 2, borderColor: colors.border },
  label: { marginTop: spacing.xs, paddingHorizontal: 1, fontSize: 10, lineHeight: 14 },
  labelCurrent: { fontFamily: "PlusJakartaSans_700Bold" },
  time: { marginTop: 2, fontSize: 9.5 },
});
