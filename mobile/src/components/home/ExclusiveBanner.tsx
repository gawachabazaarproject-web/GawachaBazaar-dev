import React from "react";
import { StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { colors, radius, shadows, spacing } from "@/theme";

/**
 * Compact promotional banner - illustrative copy (explicitly authorized),
 * no fake "Book Slot" CTA: there's no delivery-slot-booking feature in
 * this app, and a button that does nothing would violate the "don't fake
 * functionality" rule. The banner stays informational only.
 */
export function ExclusiveBanner() {
  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text variant="label" color={colors.accent}>
          GAWACHA BAZAAR EXCLUSIVE
        </Text>
        <View style={styles.cutoffPill}>
          <Feather name="clock" size={10} color={colors.primaryLight} />
          <Text variant="label" color={colors.primaryLight}>
            CUT-OFF 4:00 PM
          </Text>
        </View>
      </View>
      <Text variant="h3" color={colors.textInverse} style={styles.title}>
        Gaon se Nagpur tak.
      </Text>
      <Text variant="bodySmall" color={colors.primaryLight} style={styles.body}>
        Fresh, unadulterated harvest picked at dawn from Katol, Wardha & Saoner orchards.
      </Text>
      <View style={styles.slotRow}>
        <Feather name="truck" size={12} color={colors.primaryLight} />
        <Text variant="caption" color={colors.primaryLight}>
          Today's evening slot: 5:30 - 7:30 PM
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginHorizontal: spacing.base,
    marginTop: spacing.md,
    padding: spacing.base,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    ...shadows.raised,
  },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  cutoffPill: { flexDirection: "row", alignItems: "center", gap: 4 },
  title: { marginTop: spacing.xs },
  body: { marginTop: 2 },
  slotRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs, marginTop: spacing.sm },
});
