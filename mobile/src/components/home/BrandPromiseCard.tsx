import React from "react";
import { StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { colors, radius, spacing } from "@/theme";

/** Compact brand-trust statement - illustrative copy (explicitly
 * authorized), not a giant marketing panel. */
export function BrandPromiseCard() {
  return (
    <View style={styles.card}>
      <Feather name="award" size={16} color={colors.accent} />
      <Text variant="bodySmall" color={colors.primaryLight} style={styles.text}>
        <Text variant="titleSmall" color={colors.accent}>
          Gawacha Swad Vachan.{" "}
        </Text>
        Every rupee you spend directly empowers Vidarbha smallholders, with no middlemen
        commissions - freshness delivered in 100% recyclable craft bags.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    gap: spacing.sm,
    marginHorizontal: spacing.base,
    marginTop: spacing.md,
    padding: spacing.base,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
  },
  text: { flex: 1 },
});
