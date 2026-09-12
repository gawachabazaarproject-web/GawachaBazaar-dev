import React from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "./Text";
import { StatusPresentation } from "@/utils/statusPresentation";
import { radius, spacing } from "@/theme";

export function StatusBadge({ presentation }: { presentation: StatusPresentation }) {
  return (
    <View style={[styles.badge, { backgroundColor: presentation.backgroundColor }]}>
      <Text variant="captionMedium" color={presentation.color}>
        {presentation.label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: "flex-start",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.pill,
  },
});
