import React from "react";
import { StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "./Text";
import { colors, radius, shadows, spacing } from "@/theme";

/** Compact dark-green farm-provenance card shown after a product grid -
 * illustrative copy (explicitly authorized), reinforcing the farm-direct
 * positioning without a giant marketing panel. */
export function FreshnessStoryCard({
  title = "Picked 3 Hours Ago",
  subtitle = "Direct from Saoner & Katol FPO farmers",
}: {
  title?: string;
  subtitle?: string;
}) {
  return (
    <View style={styles.card}>
      <View style={styles.iconWrap}>
        <Feather name="truck" size={16} color={colors.accent} />
      </View>
      <View style={{ flex: 1 }}>
        <Text variant="bodyMedium" color={colors.textInverse}>
          {title}
        </Text>
        <Text variant="caption" color={colors.primaryLight}>
          {subtitle}
        </Text>
      </View>
      <Feather name="feather" size={16} color={colors.primaryLight} />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginHorizontal: spacing.base,
    marginTop: spacing.sm,
    padding: spacing.base,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    ...shadows.card,
  },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: radius.pill,
    backgroundColor: colors.primaryDark,
    alignItems: "center",
    justifyContent: "center",
  },
});
