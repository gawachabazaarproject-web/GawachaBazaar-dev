import React, { useEffect } from "react";
import { LayoutChangeEvent, Pressable, StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import { Text } from "../Text";
import { ShoppingMode } from "@/store/wholesaleStore";
import { colors, radius, spacing, timings } from "@/theme";

export interface WholesaleToggleProps {
  mode: ShoppingMode;
  onChange: (mode: ShoppingMode) => void;
}

/**
 * Big, tactile Regular/Wholesale switch - the entry point into bulk
 * ordering (see bulk_order.py: a real quote-request system, not live
 * instant checkout). A sliding pill mirrors the tab bar's own indicator
 * language rather than inventing a new control type.
 */
export function WholesaleToggle({ mode, onChange }: WholesaleToggleProps) {
  const trackWidth = useSharedValue(0);
  const progress = useSharedValue(mode === "wholesale" ? 1 : 0);

  useEffect(() => {
    progress.value = withTiming(mode === "wholesale" ? 1 : 0, timings.base);
  }, [mode, progress]);

  const onLayout = (e: LayoutChangeEvent) => {
    trackWidth.value = e.nativeEvent.layout.width;
  };

  const indicatorStyle = useAnimatedStyle(() => {
    const segmentWidth = Math.max(0, (trackWidth.value - 8) / 2);
    return {
      width: segmentWidth,
      transform: [{ translateX: progress.value * segmentWidth }],
    };
  });

  const select = (next: ShoppingMode) => {
    if (next === mode) return;
    Haptics.selectionAsync().catch(() => undefined);
    onChange(next);
  };

  return (
    <View style={styles.wrap}>
      <View style={styles.track} onLayout={onLayout}>
        <Animated.View style={[styles.indicator, indicatorStyle]} />
        <Pressable style={styles.segment} onPress={() => select("regular")} accessibilityRole="button" accessibilityState={{ selected: mode === "regular" }}>
          <Feather name="shopping-bag" size={15} color={mode === "regular" ? colors.textInverse : colors.textSecondary} />
          <Text variant="bodyMedium" color={mode === "regular" ? colors.textInverse : colors.textSecondary}>
            Regular
          </Text>
        </Pressable>
        <Pressable style={styles.segment} onPress={() => select("wholesale")} accessibilityRole="button" accessibilityState={{ selected: mode === "wholesale" }}>
          <Feather name="package" size={15} color={mode === "wholesale" ? colors.textInverse : colors.textSecondary} />
          <Text variant="bodyMedium" color={mode === "wholesale" ? colors.textInverse : colors.textSecondary}>
            Wholesale
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: spacing.base, marginTop: spacing.lg },
  track: {
    height: 52,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.divider,
    flexDirection: "row",
    padding: 4,
  },
  indicator: {
    position: "absolute",
    top: 4,
    bottom: 4,
    left: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.primary,
  },
  segment: { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.xs },
});
