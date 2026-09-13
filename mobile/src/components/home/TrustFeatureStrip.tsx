import React from "react";
import { StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { colors, radius, shadows, spacing } from "@/theme";

const FEATURES: { icon: keyof typeof Feather.glyphMap; label: string }[] = [
  { icon: "truck", label: "Farm Direct" },
  { icon: "sunrise", label: "4 AM Picked" },
  { icon: "shopping-bag", label: "Eco Bags" },
  { icon: "heart", label: "Fair Pay" },
];

/** Small informational trust strip - four compact, non-interactive
 * signals, not four giant marketing cards. */
export function TrustFeatureStrip() {
  return (
    <View style={styles.row}>
      {FEATURES.map((f) => (
        <View key={f.label} style={styles.item}>
          <Feather name={f.icon} size={16} color={colors.primary} />
          <Text variant="caption" color={colors.textSecondary} numberOfLines={1}>
            {f.label}
          </Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    marginHorizontal: spacing.base,
    marginTop: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.divider,
    paddingVertical: spacing.md,
    ...shadows.card,
  },
  item: { flex: 1, alignItems: "center", gap: spacing.xs },
});
