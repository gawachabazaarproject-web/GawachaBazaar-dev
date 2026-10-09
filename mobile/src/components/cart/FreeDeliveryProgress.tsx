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
  const unlocked = remaining <= 0;

  return (
    <View style={styles.card}>
      <View style={styles.iconCircle}>
        <Feather name="truck" size={19} color={colors.primary} />
      </View>
      <View style={styles.body}>
        <View style={styles.textRow}>
          {unlocked ? (
            <Text variant="caption" color={colors.success} style={{ flex: 1 }}>
              You've unlocked free delivery
            </Text>
          ) : (
            <Text variant="caption" color={colors.textSecondary} style={{ flex: 1 }}>
              Add {formatMoney(remaining, currency)} more for{" "}
              <Text variant="caption" color={colors.primary} style={styles.bold}>
                FREE Delivery
              </Text>
            </Text>
          )}
          <Text variant="caption" color={colors.textSecondary}>
            {Math.round(progress * 100)}%
          </Text>
        </View>
        <View style={styles.track}>
          <View style={[styles.fill, { width: `${progress * 100}%` }]} />
        </View>
      </View>
      <Feather name="chevron-right" size={18} color={colors.textSecondary} />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginHorizontal: spacing.base,
    marginTop: spacing.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: 18,
    backgroundColor: colors.surface,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  iconCircle: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  body: { flex: 1, gap: 8 },
  bold: { fontWeight: "700" },
  textRow: { flexDirection: "row", alignItems: "flex-end", gap: spacing.sm },
  track: { flex: 1, height: 6, borderRadius: radius.pill, backgroundColor: "#E8E2D3", overflow: "hidden" },
  fill: { height: "100%", backgroundColor: "#2F7A4D", borderRadius: radius.pill },
});
