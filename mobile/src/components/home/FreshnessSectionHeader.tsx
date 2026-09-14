import React from "react";
import { StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { colors, radius, spacing } from "@/theme";

/**
 * "Today's Morning Harvest" section header - illustrative freshness
 * framing (explicitly authorized) around the real products rendered
 * beneath it; the LIVE dot and "2 hrs left" are presentation only, not
 * backed by an actual harvest-timing system.
 */
export function FreshnessSectionHeader() {
  return (
    <View style={styles.wrap}>
      <View style={styles.titleRow}>
        <Text variant="h2">Today's Morning Harvest</Text>
        <View style={styles.livePill}>
          <View style={styles.liveDot} />
          <Text variant="label" color={colors.error}>
            LIVE
          </Text>
        </View>
      </View>
      <View style={styles.metaRow}>
        <Text variant="caption" color={colors.textSecondary}>
          Picked at 4 AM · Direct from Saoner mandis
        </Text>
        <View style={styles.timerPill}>
          <Feather name="clock" size={10} color={colors.textSecondary} />
          <Text variant="caption" color={colors.textSecondary}>
            2 hrs left
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: spacing.base, marginTop: spacing.xl, marginBottom: spacing.md },
  titleRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  livePill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: colors.errorLight,
    borderRadius: radius.xs,
    paddingHorizontal: spacing.xs,
    paddingVertical: 3,
  },
  liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.error },
  metaRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 2 },
  timerPill: { flexDirection: "row", alignItems: "center", gap: 3 },
});
