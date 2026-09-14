import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { colors, radius, spacing } from "@/theme";

export interface DeliverySummaryCardProps {
  addressLabel: string;
  addressLine: string;
  onChangePress: () => void;
}

/** Compact delivery-address summary at the top of the cart - real
 * address data, "Estimated in 25 mins" is the same illustrative ETA
 * framing used elsewhere in the app. */
export function DeliverySummaryCard({ addressLabel, addressLine, onChangePress }: DeliverySummaryCardProps) {
  return (
    <View style={styles.card}>
      <View style={styles.iconWrap}>
        <Feather name="map-pin" size={14} color={colors.primary} />
      </View>
      <View style={{ flex: 1 }}>
        <Text variant="label" color={colors.textSecondary}>
          DELIVERING TO {addressLabel.toUpperCase()}
        </Text>
        <Text variant="bodyMedium" numberOfLines={1}>
          {addressLine}
        </Text>
        <Text variant="caption" color={colors.textSecondary}>
          Estimated in 25 mins from Saoner Mandi Hub
        </Text>
      </View>
      <Pressable onPress={onChangePress}>
        <Text variant="bodySmall" color={colors.primary}>
          Change
        </Text>
      </Pressable>
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
    paddingVertical: spacing.base,
    borderBottomWidth: 1,
    borderColor: colors.divider,
  },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: radius.none,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
});
