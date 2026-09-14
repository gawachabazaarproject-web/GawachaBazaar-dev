import React from "react";
import { StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { colors, radius, spacing } from "@/theme";

/** "Local Vidarbha Impact" brand-trust card - illustrative copy
 * (explicitly authorized), not tied to a real farmer-count field. */
export function ImpactCard() {
  return (
    <View style={styles.card}>
      <View style={styles.iconWrap}>
        <Feather name="users" size={16} color={colors.primary} />
      </View>
      <View style={{ flex: 1 }}>
        <Text variant="bodyMedium" color={colors.textInverse}>
          Local Vidarbha Impact
        </Text>
        <Text variant="caption" color={colors.primaryLight} style={{ marginTop: 2 }}>
          This order directly supports smallholder farmers in Saoner & Katol villages. No
          middlemen involved.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    gap: spacing.sm,
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    padding: spacing.base,
    marginBottom: spacing.base,
  },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: radius.pill,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
});
