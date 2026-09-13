import React from "react";
import { Pressable, PressableProps, StyleProp, ViewStyle } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from "react-native-reanimated";
import * as Haptics from "expo-haptics";
import { springs } from "@/theme";

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

export interface PressableScaleProps extends PressableProps {
  style?: StyleProp<ViewStyle>;
  /** Pass null to skip haptics (e.g. for large content areas). */
  hapticStyle?: Haptics.ImpactFeedbackStyle | null;
  scaleTo?: number;
}

/** Shared press-scale interaction (spring down on press, spring back on
 * release) for tappable cards/tiles that aren't already a Button -
 * category tiles, product cards, buy-again cards. Keeps every "tappable
 * surface" in the app feeling consistent without re-deriving the spring
 * math per screen. */
export function PressableScale({
  children,
  style,
  onPressIn,
  onPressOut,
  hapticStyle = Haptics.ImpactFeedbackStyle.Light,
  scaleTo = 0.96,
  ...rest
}: PressableScaleProps) {
  const scale = useSharedValue(1);
  const animatedStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));

  return (
    <AnimatedPressable
      style={[style, animatedStyle]}
      onPressIn={(e) => {
        scale.value = withSpring(scaleTo, springs.snappy);
        onPressIn?.(e);
      }}
      onPressOut={(e) => {
        scale.value = withSpring(1, springs.snappy);
        onPressOut?.(e);
      }}
      onPress={(e) => {
        if (hapticStyle) Haptics.impactAsync(hapticStyle);
        rest.onPress?.(e);
      }}
      {...rest}
    >
      {children}
    </AnimatedPressable>
  );
}
