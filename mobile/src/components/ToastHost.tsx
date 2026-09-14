import React, { useEffect } from "react";
import { StyleSheet } from "react-native";
import Animated, { FadeInUp, FadeOutUp } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Text } from "./Text";
import { useToastStore } from "@/store/toastStore";
import { colors, radius, shadows, spacing } from "@/theme";

const TONE_COLOR: Record<string, string> = {
  default: colors.textPrimary,
  error: colors.error,
  success: colors.success,
};

/** Renders once, at the root layout - any screen can call
 * useToastStore.getState().show(...) without prop drilling. */
export function ToastHost() {
  const { message, tone, hide } = useToastStore();
  const insets = useSafeAreaInsets();

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(hide, 3000);
    return () => clearTimeout(timer);
  }, [message, hide]);

  if (!message) return null;

  return (
    <Animated.View
      entering={FadeInUp.duration(200)}
      exiting={FadeOutUp.duration(180)}
      style={[styles.toast, { top: insets.top + spacing.sm, borderLeftColor: TONE_COLOR[tone] }]}
      pointerEvents="none"
    >
      <Text variant="bodyMedium">{message}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  toast: {
    position: "absolute",
    left: spacing.base,
    right: spacing.base,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderLeftWidth: 4,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.base,
    ...shadows.raised,
    zIndex: 100,
  },
});
