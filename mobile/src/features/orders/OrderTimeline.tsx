import React from "react";
import { StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { colors, spacing } from "@/theme";
import { FulfillmentStatus, OrderStatus } from "@/types/api";

interface Step {
  key: string;
  label: string;
  done: boolean;
}

const FULFILLMENT_ORDER: FulfillmentStatus[] = [
  "PENDING",
  "PICKING",
  "PACKED",
  "READY_FOR_DELIVERY",
  "ASSIGNED",
  "OUT_FOR_DELIVERY",
  "DELIVERED",
];

/**
 * State-based tracking timeline (brief §32) - four milestones derived
 * directly from the backend's own Order/Fulfillment status values. No
 * GPS, no live driver location, no fake ETA - just an honest reflection
 * of "how far along is this order", which is all the current backend
 * actually knows.
 */
export function OrderTimeline({
  orderStatus,
  fulfillmentStatus,
}: {
  orderStatus: OrderStatus;
  fulfillmentStatus: FulfillmentStatus | null;
}) {
  if (orderStatus === "CANCELLED") {
    return <StatusBanner icon="x-circle" color={colors.error} label="This order was cancelled" />;
  }
  if (orderStatus === "EXPIRED") {
    return <StatusBanner icon="clock" color={colors.textMuted} label="This order expired before payment was completed" />;
  }

  const fulfillmentIndex = fulfillmentStatus ? FULFILLMENT_ORDER.indexOf(fulfillmentStatus) : -1;
  const confirmed = orderStatus === "CONFIRMED" || orderStatus === "COMPLETED";

  const steps: Step[] = [
    { key: "placed", label: "Order placed", done: true },
    { key: "confirmed", label: "Confirmed", done: confirmed },
    { key: "preparing", label: "Preparing your order", done: confirmed && fulfillmentIndex >= 1 },
    { key: "out_for_delivery", label: "Out for delivery", done: fulfillmentIndex >= 5 },
    { key: "delivered", label: "Delivered", done: fulfillmentIndex >= 6 || orderStatus === "COMPLETED" },
  ];

  const activeIndex = steps.reduce((acc, step, idx) => (step.done ? idx : acc), 0);

  return (
    <View>
      {steps.map((step, idx) => {
        const isLast = idx === steps.length - 1;
        return (
          <View key={step.key} style={styles.row}>
            <View style={styles.indicatorColumn}>
              <View
                style={[
                  styles.dot,
                  step.done && styles.dotDone,
                  idx === activeIndex && styles.dotActive,
                ]}
              >
                {step.done ? <Feather name="check" size={11} color={colors.textInverse} /> : null}
              </View>
              {!isLast ? <View style={[styles.line, step.done && idx < activeIndex ? styles.lineDone : null]} /> : null}
            </View>
            <Text
              variant={idx === activeIndex ? "bodyMedium" : "body"}
              color={step.done ? colors.textPrimary : colors.textMuted}
              style={styles.label}
            >
              {step.label}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

function StatusBanner({ icon, color, label }: { icon: keyof typeof Feather.glyphMap; color: string; label: string }) {
  return (
    <View style={styles.banner}>
      <Feather name={icon} size={20} color={color} />
      <Text variant="bodyMedium" color={color} style={{ marginLeft: spacing.sm }}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", minHeight: 44 },
  indicatorColumn: { alignItems: "center", width: 24 },
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
  dotActive: { borderColor: colors.primary },
  line: { width: 2, flex: 1, backgroundColor: colors.border, marginVertical: 2 },
  lineDone: { backgroundColor: colors.success },
  label: { marginLeft: spacing.md, paddingTop: 2 },
  banner: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.md,
    borderRadius: 12,
    backgroundColor: colors.divider,
  },
});
