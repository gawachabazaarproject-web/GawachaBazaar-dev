import React from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "./Text";
import { colors, spacing } from "@/theme";

export interface RecommendationRailProps {
  title: string;
  subtitle?: string;
  onSeeAll?: () => void;
  children: React.ReactNode;
}

/** Horizontal scrollable rail wrapper - used for "Pairs with Tomatoes"
 * and "Village Mandi Add-ons" style recommendation strips. */
export function RecommendationRail({ title, subtitle, onSeeAll, children }: RecommendationRailProps) {
  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text variant="h3">{title}</Text>
          {subtitle ? (
            <Text variant="caption" color={colors.textSecondary} style={{ marginTop: 2 }}>
              {subtitle}
            </Text>
          ) : null}
        </View>
        {onSeeAll ? (
          <Pressable onPress={onSeeAll} style={styles.seeAll}>
            <Text variant="bodySmall" color={colors.primary}>
              See All
            </Text>
            <Feather name="arrow-right" size={12} color={colors.primary} />
          </Pressable>
        ) : null}
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        {children}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: spacing.lg },
  header: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    paddingHorizontal: spacing.base,
    marginBottom: spacing.sm,
  },
  seeAll: { flexDirection: "row", alignItems: "center", gap: 4 },
  scroll: { paddingHorizontal: spacing.base, gap: spacing.sm },
});
