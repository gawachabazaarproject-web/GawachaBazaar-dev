import React from "react";
import { ActivityIndicator, Pressable, StyleSheet, View, ViewStyle } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from "react-native-reanimated";
import * as Haptics from "expo-haptics";
import { Text } from "./Text";
import { colors, radius, spacing, springs } from "@/theme";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger";
type Size = "md" | "lg";

export interface ButtonProps {
  label: string;
  onPress: () => void;
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  disabled?: boolean;
  fullWidth?: boolean;
  icon?: React.ReactNode;
  style?: ViewStyle;
  hapticStyle?: Haptics.ImpactFeedbackStyle | null;
}

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

/** The single button primitive for the app. Every variant shares the same
 * press animation (scale down slightly, spring back) and haptic - visual
 * consistency across every CTA in the product. */
export function Button({
  label,
  onPress,
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  fullWidth = false,
  icon,
  style,
  hapticStyle = Haptics.ImpactFeedbackStyle.Light,
}: ButtonProps) {
  const scale = useSharedValue(1);
  const isDisabled = disabled || loading;

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));

  const handlePressIn = () => {
    if (isDisabled) return;
    scale.value = withSpring(0.97, springs.snappy);
  };
  const handlePressOut = () => {
    scale.value = withSpring(1, springs.snappy);
  };
  const handlePress = () => {
    if (isDisabled) return;
    if (hapticStyle) Haptics.impactAsync(hapticStyle);
    onPress();
  };

  const variantStyle = VARIANT_STYLES[variant];
  const textColor = isDisabled ? colors.textMuted : variantStyle.textColor;

  return (
    <AnimatedPressable
      onPress={handlePress}
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
      disabled={isDisabled}
      accessibilityRole="button"
      accessibilityState={{ disabled: isDisabled, busy: loading }}
      accessibilityLabel={label}
      style={[
        styles.base,
        SIZE_STYLES[size],
        variantStyle.container,
        isDisabled && variant !== "ghost" && styles.disabledContainer,
        fullWidth && styles.fullWidth,
        animatedStyle,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={textColor} size="small" />
      ) : (
        <View style={styles.content}>
          {icon}
          <Text variant="button" color={textColor}>
            {label}
          </Text>
        </View>
      )}
    </AnimatedPressable>
  );
}

const VARIANT_STYLES: Record<Variant, { container: ViewStyle; textColor: string }> = {
  primary: { container: { backgroundColor: colors.primary }, textColor: colors.textInverse },
  secondary: { container: { backgroundColor: colors.accent }, textColor: colors.textOnAccent },
  outline: {
    container: { backgroundColor: colors.transparent, borderWidth: 1.5, borderColor: colors.primary },
    textColor: colors.primary,
  },
  ghost: { container: { backgroundColor: colors.transparent }, textColor: colors.primary },
  danger: { container: { backgroundColor: colors.error }, textColor: colors.textInverse },
};

const SIZE_STYLES: Record<Size, ViewStyle> = {
  md: { paddingVertical: spacing.md, paddingHorizontal: spacing.lg },
  lg: { paddingVertical: spacing.base, paddingHorizontal: spacing.xl },
};

const styles = StyleSheet.create({
  base: {
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  content: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  disabledContainer: { opacity: 0.45 },
  fullWidth: { width: "100%" },
});
