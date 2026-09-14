import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import Animated, { FadeInDown, FadeOutDown } from "react-native-reanimated";
import { Feather } from "@expo/vector-icons";
import { useRouter, useSegments } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Text } from "../Text";
import { useWholesaleStore } from "@/store/wholesaleStore";
import { colors, radius, shadows, spacing } from "@/theme";

const TAB_BAR_CONTENT_HEIGHT = 64;

/**
 * Wholesale twin of CartBar - floats above the tab bar while the customer
 * is building up a bulk order request draft, and disappears the moment
 * it's empty or they switch back to regular mode. Never shows alongside
 * CartBar (see CartBar.tsx's own mode check).
 */
export function BulkRequestBar() {
  const router = useRouter();
  const segments = useSegments();
  const insets = useSafeAreaInsets();
  const mode = useWholesaleStore((s) => s.mode);
  const draftItems = useWholesaleStore((s) => s.draftItems);

  const inTabs = segments[0] === "(tabs)";
  const rootSegment = segments[0];
  const hiddenOnScreen = rootSegment === "bulk";

  if (mode !== "wholesale" || draftItems.length === 0 || hiddenOnScreen) return null;

  const bottomOffset = inTabs ? TAB_BAR_CONTENT_HEIGHT + insets.bottom : insets.bottom + spacing.base;

  return (
    <Animated.View
      entering={FadeInDown.duration(220)}
      exiting={FadeOutDown.duration(180)}
      style={[styles.wrap, { bottom: bottomOffset }]}
      pointerEvents="box-none"
    >
      <Pressable style={styles.bar} onPress={() => router.push("/bulk/review")} accessibilityRole="button" accessibilityLabel="Review bulk request">
        <View style={styles.left}>
          <Text variant="label" color={colors.accentLight}>
            BULK REQUEST
          </Text>
          <Text variant="bodyMedium" color={colors.textInverse}>
            {draftItems.length} {draftItems.length === 1 ? "item" : "items"} added
          </Text>
        </View>
        <View style={styles.right}>
          <Text variant="bodyMedium" color={colors.textInverse}>
            Review
          </Text>
          <View style={styles.ctaPill}>
            <Feather name="arrow-right" size={15} color={colors.textOnAccent} />
          </View>
        </View>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: "absolute", left: 0, right: 0, paddingHorizontal: spacing.md },
  bar: {
    height: 56,
    backgroundColor: colors.primary,
    borderRadius: radius.none,
    borderWidth: 1,
    borderColor: colors.primaryDark,
    paddingHorizontal: spacing.base,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    ...shadows.raised,
  },
  left: { justifyContent: "center", gap: 2 },
  right: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  ctaPill: {
    width: 28,
    height: 28,
    borderRadius: radius.pill,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
});
