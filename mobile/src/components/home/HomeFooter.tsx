import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "../Text";
import { OfferCarousel } from "./OfferCarousel";
import { CART_BAR_CLEARANCE } from "../CartBar";
import { colors, radius, spacing } from "@/theme";

const PROMISES: { icon: keyof typeof Feather.glyphMap; title: string; body: string }[] = [
  { icon: "truck", title: "Farm-direct delivery", body: "From the field to your door the same day." },
  { icon: "heart", title: "Fair pay to growers", body: "No middlemen - more of every rupee reaches the farm." },
  { icon: "package", title: "Zero single-use plastic", body: "Packed in returnable jute crates." },
];

export interface HomeFooterProps {
  onBackToTop: () => void;
}

/**
 * Closes the Home screen. Continues the dark brand panel above it (so the
 * page never ends in blank space), restates what the shopper gets, and
 * carries the bottom clearance for the floating cart bar / tab bar.
 */
export function HomeFooter({ onBackToTop }: HomeFooterProps) {
  return (
    <View style={styles.wrap}>
      <OfferCarousel />
      <View style={styles.body}>
      <View style={styles.rule} />

      {PROMISES.map((p) => (
        <View key={p.title} style={styles.promise}>
          <View style={styles.iconCircle}>
            <Feather name={p.icon} size={18} color={colors.accentLight} />
          </View>
          <View style={styles.promiseText}>
            <Text variant="bodyMedium" color={colors.textInverse}>
              {p.title}
            </Text>
            <Text variant="bodySmall" color="rgba(255,255,255,0.65)" style={styles.promiseBody}>
              {p.body}
            </Text>
          </View>
        </View>
      ))}

      <Pressable
        onPress={onBackToTop}
        style={({ pressed }) => [styles.topButton, pressed && { opacity: 0.8 }]}
        accessibilityRole="button"
        accessibilityLabel="Back to top"
      >
        <Feather name="arrow-up" size={15} color={colors.accentLight} />
        <Text variant="eyebrow" color={colors.accentLight}>
          BACK TO TOP
        </Text>
      </Pressable>

      <Text variant="caption" color="rgba(255,255,255,0.45)" style={styles.legal}>
        {`© ${new Date().getFullYear()} Gawacha Bazaar · Fresh from Vidarbha, delivered in Nagpur`}
      </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  // Same colour as ClosingCTA so the two read as one continuous panel.
  wrap: {
    backgroundColor: colors.primary,
    paddingBottom: spacing.xl + CART_BAR_CLEARANCE,
  },
  body: { paddingHorizontal: spacing.base },
  rule: { height: 1, backgroundColor: "rgba(255,255,255,0.12)", marginTop: spacing["2xl"], marginBottom: spacing.xl },
  promise: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginBottom: spacing.lg },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(255,255,255,0.08)",
    alignItems: "center",
    justifyContent: "center",
  },
  promiseText: { flex: 1 },
  promiseBody: { marginTop: 2 },
  topButton: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.md,
    paddingVertical: spacing.sm + 2,
    paddingHorizontal: spacing.base,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: "rgba(255,222,162,0.5)",
  },
  legal: { marginTop: spacing.xl },
});
