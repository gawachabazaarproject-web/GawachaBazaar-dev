import React, { useEffect } from "react";
import { StyleSheet, View, ViewStyle } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";
import { colors, radius } from "@/theme";

export interface SkeletonProps {
  width?: number | `${number}%`;
  height?: number;
  borderRadius?: number;
  style?: ViewStyle;
}

/** Subtle shimmer block used everywhere loading content has a known
 * shape (product cards, order rows, product detail) - never a bare
 * spinner for content that has real layout. */
export function Skeleton({ width = "100%", height = 16, borderRadius = radius.sm, style }: SkeletonProps) {
  const opacity = useSharedValue(0.5);

  useEffect(() => {
    opacity.value = withRepeat(withTiming(1, { duration: 700 }), -1, true);
  }, [opacity]);

  const animatedStyle = useAnimatedStyle(() => ({ opacity: opacity.value }));

  return (
    <Animated.View
      style={[{ width, height, borderRadius, backgroundColor: colors.divider }, animatedStyle, style]}
    />
  );
}

export function SkeletonCircle({ size = 40 }: { size?: number }) {
  return <Skeleton width={size} height={size} borderRadius={size / 2} />;
}

/** Skeleton shape matching ProductCard, for grid/list loading states. */
export function ProductCardSkeleton() {
  return (
    <View style={styles.card}>
      <Skeleton height={110} borderRadius={radius.none} />
      <View style={{ height: 8 }} />
      <Skeleton height={13} width="90%" />
      <View style={{ height: 6 }} />
      <Skeleton height={13} width="60%" />
      <View style={{ height: 10 }} />
      <Skeleton height={16} width="40%" />
    </View>
  );
}

const styles = StyleSheet.create({
  card: { flex: 1, padding: 4 },
});
