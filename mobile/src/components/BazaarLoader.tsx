import React, { useEffect } from "react";
import { StyleSheet, View } from "react-native";
import Animated, {
  Easing,
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";
import { colors } from "@/theme";

interface BazaarLoaderProps {
  /** Dot colours, cycled left to right. Defaults to the brand green/gold/leaf. */
  palette?: string[];
  size?: number;
}

const STEP_MS = 130;
const UP_MS = 260;
const DOWN_MS = 300;
const REST_MS = 260;

function Dot({ index, color, size }: { index: number; color: string; size: number }) {
  const lift = useSharedValue(0);

  useEffect(() => {
    lift.value = withDelay(
      index * STEP_MS,
      withRepeat(
        withSequence(
          withTiming(1, { duration: UP_MS, easing: Easing.out(Easing.quad) }),
          withTiming(0, { duration: DOWN_MS, easing: Easing.bounce }),
          withTiming(0, { duration: REST_MS }),
        ),
        -1,
      ),
    );
    return () => cancelAnimation(lift);
  }, [index, lift]);

  // Rises and stretches on the way up, lands with a squash - reads as a
  // bouncing piece of produce rather than a generic spinner.
  const style = useAnimatedStyle(() => ({
    transform: [
      { translateY: -lift.value * size * 0.9 },
      { scaleX: 1 - lift.value * 0.15 },
      { scaleY: 1 + lift.value * 0.25 },
    ],
  }));

  return (
    <Animated.View
      style={[{ width: size, height: size, borderRadius: size / 2, backgroundColor: color }, style]}
    />
  );
}

/** Three dots hopping in a wave. Drop-in replacement for ActivityIndicator
 * wherever an action is in flight. */
export function BazaarLoader({ palette, size = 8 }: BazaarLoaderProps) {
  const dots = palette ?? [colors.primaryLight, colors.accent, colors.textInverse];
  return (
    <View style={[styles.row, { height: size * 2.4, gap: size * 0.7 }]} accessibilityRole="progressbar">
      {dots.slice(0, 3).map((c, i) => (
        <Dot key={i} index={i} color={c} size={size} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "flex-end", justifyContent: "center", paddingBottom: 2 },
});
