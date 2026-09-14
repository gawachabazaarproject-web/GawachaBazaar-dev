import React from "react";
import { StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "../Text";
import { colors, spacing } from "@/theme";

const FEATURES: { icon: keyof typeof Feather.glyphMap; label: string }[] = [
  { icon: "truck", label: "Farm Direct" },
  { icon: "sunrise", label: "4 AM Picked" },
  { icon: "shopping-bag", label: "Eco Bags" },
  { icon: "heart", label: "Fair Pay" },
];

/**
 * Editorial brand statement - the same real copy previously shown in the
 * old BrandPromiseCard/TrustFeatureStrip boxed cards ("Gawacha Swad
 * Vachan.", the four trust signals), now given full-width editorial
 * typography instead of a small dark card.
 */
export function BrandStatement() {
  return (
    <View style={styles.wrap}>
      <Text variant="eyebrow" color={colors.accentDark}>
        OUR PROMISE
      </Text>
      <Text variant="displayM" style={styles.headline}>
        <Text variant="script" color={colors.primary}>
          Gawacha Swad Vachan.
        </Text>
      </Text>
      <Text variant="body" color={colors.textSecondary} style={styles.body}>
        Every rupee you spend directly empowers Vidarbha smallholders, with no middlemen
        commissions - freshness delivered in 100% recyclable craft bags.
      </Text>
      <View style={styles.featureRow}>
        {FEATURES.map((f) => (
          <View key={f.label} style={styles.feature}>
            <Feather name={f.icon} size={16} color={colors.primary} />
            <Text variant="caption" color={colors.textSecondary} numberOfLines={1}>
              {f.label}
            </Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: spacing.base, paddingVertical: spacing["3xl"] },
  headline: { marginTop: spacing.sm },
  body: { marginTop: spacing.base, maxWidth: "92%" },
  featureRow: {
    flexDirection: "row",
    marginTop: spacing["2xl"],
    paddingTop: spacing.xl,
    borderTopWidth: 1,
    borderColor: colors.divider,
  },
  feature: { flex: 1, alignItems: "center", gap: spacing.xs },
});
