import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { colors, spacing } from "@/theme";

export interface DeliverySummaryCardProps {
  addressLabel: string;
  addressLine: string;
  onChangePress: () => void;
}

/** Delivery-address block at the top of the cart - real address data;
 * "Estimated in 25 mins" is the same illustrative ETA used elsewhere. */
export function DeliverySummaryCard({ addressLabel, addressLine, onChangePress }: DeliverySummaryCardProps) {
  return (
    <Pressable onPress={onChangePress} accessibilityRole="button" accessibilityLabel="Change delivery address">
      <View style={styles.row}>
        <Feather name="map-pin" size={22} color={colors.accentDark} />
        <View style={styles.textCol}>
          <Text variant="label" color={colors.textSecondary} style={styles.eyebrow}>
            DELIVERING TO
          </Text>
          <View style={styles.titleRow}>
            <Text variant="h3" numberOfLines={1} style={styles.title}>
              {addressLine || addressLabel}
            </Text>
            <Feather name="chevron-down" size={16} color={colors.textPrimary} />
          </View>
        </View>
      </View>
      <Text
        variant="caption"
        color={colors.textSecondary}
        numberOfLines={1}
        adjustsFontSizeToFit
        minimumFontScale={0.8}
        style={styles.eta}
      >
        Estimated in 25 mins from Saoner Mandi Hub
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  textCol: { flexShrink: 1 },
  eyebrow: { letterSpacing: 1.2 },
  titleRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
  title: { flexShrink: 1 },
  // Indented to line up with the text column (icon 20 + gap 8).
  eta: { marginTop: 3, marginLeft: 28, fontSize: 11.5 },
});
