import React from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "./Text";
import { StatusPresentation } from "@/utils/statusPresentation";
import { spacing } from "@/theme";

/** Restrained status indicator - a small dot + label rather than a
 * filled, brightly-colored pill, per the editorial "no excessively
 * colorful status badges" direction. */
export function StatusBadge({ presentation }: { presentation: StatusPresentation }) {
  return (
    <View style={styles.badge}>
      <View style={[styles.dot, { backgroundColor: presentation.color }]} />
      <Text variant="captionMedium" color={presentation.color}>
        {presentation.label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: { flexDirection: "row", alignItems: "center", alignSelf: "flex-start", gap: spacing.xs },
  dot: { width: 6, height: 6, borderRadius: 3 },
});
