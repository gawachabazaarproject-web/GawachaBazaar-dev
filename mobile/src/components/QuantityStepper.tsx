import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import Animated, {
  FadeIn,
  FadeOut,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
} from "react-native-reanimated";
import * as Haptics from "expo-haptics";
import { Feather } from "@expo/vector-icons";
import { Text } from "./Text";
import { colors, radius, springs } from "@/theme";

export interface QuantityStepperProps {
  /** null/undefined means "not in cart yet" - renders the compact ADD button. */
  quantity: number | null;
  onAdd: () => void;
  onIncrement: () => void;
  onDecrement: () => void;
  disabled?: boolean;
  compact?: boolean;
  /** Stretches to the width of its container instead of sizing to
   * content - used for the compact 2-column product card footer, where
   * the control should span the card like the reference design. */
  fullWidth?: boolean;
}

/**
 * The Product -> ADD -> stepper interaction described in the brief. A
 * bare "ADD" pill morphs into a +/- stepper the moment the item enters
 * the cart, and back again when quantity reaches zero - one component
 * handles the whole lifecycle so every product card/detail screen
 * behaves identically.
 */
export function QuantityStepper({
  quantity,
  onAdd,
  onIncrement,
  onDecrement,
  disabled,
  compact = true,
  fullWidth = false,
}: QuantityStepperProps) {
  const scale = useSharedValue(1);
  const bump = () => {
    scale.value = withSpring(1.12, springs.snappy, () => {
      scale.value = withSpring(1, springs.snappy);
    });
  };
  const animatedStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));

  const height = compact ? 32 : 40;

  if (quantity === null || quantity === undefined || quantity <= 0) {
    return (
      <Animated.View
        entering={FadeIn.duration(150)}
        exiting={FadeOut.duration(120)}
        style={fullWidth && styles.fullWidth}
      >
        <Pressable
          disabled={disabled}
          onPress={() => {
            Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
            bump();
            onAdd();
          }}
          style={[
            styles.addButton,
            { height },
            fullWidth && styles.fullWidth,
            disabled && styles.disabled,
          ]}
          accessibilityRole="button"
          accessibilityLabel="Add to cart"
        >
          <Animated.View style={animatedStyle}>
            <Text variant="button" color={colors.primary}>
              ADD
            </Text>
          </Animated.View>
        </Pressable>
      </Animated.View>
    );
  }

  return (
    <Animated.View
      entering={FadeIn.duration(150)}
      style={[styles.stepper, { height }, fullWidth && styles.fullWidth]}
    >
      <Pressable
        onPress={() => {
          Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
          onDecrement();
        }}
        style={styles.stepperButton}
        accessibilityRole="button"
        accessibilityLabel="Decrease quantity"
        hitSlop={8}
      >
        <Feather name="minus" size={15} color={colors.textInverse} />
      </Pressable>
      <Animated.View style={[styles.quantityWrap, fullWidth && { flex: 1 }, animatedStyle]}>
        <Text variant="bodyMedium" color={colors.textInverse}>
          {quantity}
        </Text>
      </Animated.View>
      <Pressable
        onPress={() => {
          Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
          bump();
          onIncrement();
        }}
        style={styles.stepperButton}
        accessibilityRole="button"
        accessibilityLabel="Increase quantity"
        hitSlop={8}
      >
        <Feather name="plus" size={15} color={colors.textInverse} />
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  fullWidth: { width: "100%" },
  addButton: {
    borderRadius: radius.none,
    borderWidth: 1,
    borderColor: colors.primary,
    paddingHorizontal: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
  },
  disabled: { opacity: 0.4 },
  stepper: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: radius.none,
    backgroundColor: colors.primary,
    minWidth: 88,
    justifyContent: "space-between",
  },
  stepperButton: { paddingHorizontal: 10, height: "100%", alignItems: "center", justifyContent: "center" },
  quantityWrap: { alignItems: "center", justifyContent: "center", minWidth: 20 },
});
