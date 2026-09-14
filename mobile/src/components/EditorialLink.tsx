import React from "react";
import { Pressable, PressableProps, StyleProp, StyleSheet, View, ViewStyle } from "react-native";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import { Text } from "./Text";
import { colors, spacing } from "@/theme";

export interface EditorialLinkProps extends Omit<PressableProps, "style"> {
  children: string;
  tone?: "dark" | "light";
  style?: StyleProp<ViewStyle>;
}

/** The app's one text-link CTA - underline + arrow, matches the website's
 * EditorialLink component. Used for "Explore →" / "View all →" instead of
 * pill-shaped buttons, which the design language avoids. */
export function EditorialLink({ children, tone = "dark", style, onPressIn, onPressOut, ...rest }: EditorialLinkProps) {
  const progress = useSharedValue(1);
  const color = tone === "dark" ? colors.primary : colors.textInverse;

  const lineStyle = useAnimatedStyle(() => ({
    transform: [{ scaleX: progress.value }],
  }));

  return (
    <Pressable
      accessibilityRole="button"
      onPressIn={(e) => {
        progress.value = withTiming(0.35, { duration: 120 });
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => undefined);
        onPressIn?.(e);
      }}
      onPressOut={(e) => {
        progress.value = withTiming(1, { duration: 220 });
        onPressOut?.(e);
      }}
      style={[styles.wrap, style]}
      {...rest}
    >
      <View>
        <Text variant="eyebrow" color={color}>
          {children}
        </Text>
        <View style={[styles.lineTrack, { backgroundColor: tone === "dark" ? colors.divider : "rgba(255,255,255,0.2)" }]} />
        <Animated.View style={[styles.line, { backgroundColor: color }, lineStyle]} />
      </View>
      <Feather name="arrow-right" size={13} color={color} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: "row", alignItems: "center", gap: spacing.sm, alignSelf: "flex-start" },
  lineTrack: { height: 1, marginTop: 5 },
  line: { height: 1, marginTop: -1, transformOrigin: "left" },
});
