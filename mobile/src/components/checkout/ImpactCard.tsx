import React from "react";
import { StyleSheet, View } from "react-native";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { colors, spacing } from "@/theme";

/** "Local Vidarbha Impact" brand-trust card - illustrative copy
 * (explicitly authorized), not tied to a real farmer-count field. */
export function ImpactCard() {
  return (
    <View style={styles.card}>
      <View style={styles.iconWrap}>
        <MaterialCommunityIcons name="account-group" size={24} color={colors.primary} />
      </View>
      <View style={{ flex: 1 }}>
        <Text variant="bodyMedium">Local Vidarbha Impact</Text>
        <Text variant="caption" color={colors.textSecondary} style={{ marginTop: 2 }}>
          This order directly supports smallholder farmers in Saoner & Katol villages. No middlemen involved.
        </Text>
      </View>
      <MaterialCommunityIcons name="sprout" size={34} color="rgba(47,122,77,0.45)" />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: "#EEF0E9",
    borderRadius: 16,
    padding: spacing.md,
    marginTop: spacing.md,
  },
  iconWrap: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.accentLight,
    alignItems: "center",
    justifyContent: "center",
  },
});
