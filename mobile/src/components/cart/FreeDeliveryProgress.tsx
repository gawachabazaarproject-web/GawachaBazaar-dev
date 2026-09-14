import React from "react";
import { StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { formatMoney } from "@/utils/money";
import { colors, radius, spacing } from "@/theme";

/** Illustrative free-delivery threshold (explicitly authorized) - the
 * backend has no delivery-fee concept at all (checkout never charges
 * one), so this is presentational encouragement only, computed from the
 * real cart total against a made-up target. */
const FREE_DELIVERY_THRESHOLD = 300;

export function FreeDeliveryProgress({ cartTotal, currency = "INR" }: { cartTotal: number; currency?: string }) {
  const remaining = Math.max(0, FREE_DELIVERY_THRESHOLD - cartTotal);
  const progress = Math.min(1, cartTotal / FREE_DELIVERY_THRESHOLD);

  if (remaining <= 0) {
    return (
      <View style={styles.wrap}>
        <View style={styles.row}>
          <Feather name="check-circle" size={13} color={colors.success} />
          <Text variant="caption" color={colors.success}>
            You've unlocked free delivery
          </Text>
        </View>
        <View style={styles.track}>
          <View style={[styles.fill, { width: "100%" }]} />
        </View>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.row}>
        <Text variant="caption" color={colors.textSecondary} style={{ flex: 1 }}>
          Add {formatMoney(remaining, currency)} more for{" "}
          <Text variant="captionMedium" color={colors.accentDark}>
            FREE Delivery
          </Text>
        </Text>
        <Text variant="caption" color={colors.textSecondary}>
          {Math.round(progress * 100)}%
        </Text>
      </View>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${progress * 100}%` }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginHorizontal: spacing.base, marginTop: spacing.sm },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.xs, marginBottom: 4 },
  track: { height: 5, borderRadius: radius.pill, backgroundColor: colors.divider, overflow: "hidden" },
  fill: { height: "100%", backgroundColor: colors.accent, borderRadius: radius.pill },
});
