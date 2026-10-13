import React, { useEffect, useState } from "react";
import { Modal, StyleSheet, View } from "react-native";
import Animated, {
  Easing,
  FadeIn,
  FadeInDown,
  FadeOutUp,
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";
import { Feather } from "@expo/vector-icons";
import { BazaarLoader } from "@/components/BazaarLoader";
import { Text } from "@/components/Text";
import { colors, radius, spacing } from "@/theme";

const STEPS = [
  "Reserving your fresh produce…",
  "Packing it into a jute crate…",
  "Confirming with the mandi…",
  "Almost there…",
];
const STEP_MS = 2500;

/** Full-screen blocking loader shown while an order is being placed, so the
 * customer sees progress (and can't double-tap) instead of a frozen screen. */
export function PlacingOrderOverlay({ visible }: { visible: boolean }) {
  const [step, setStep] = useState(0);
  const bob = useSharedValue(0);
  const pulse = useSharedValue(0);

  useEffect(() => {
    if (!visible) {
      setStep(0);
      return;
    }
    const id = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), STEP_MS);
    bob.value = withRepeat(
      withSequence(
        withTiming(1, { duration: 600, easing: Easing.out(Easing.quad) }),
        withTiming(0, { duration: 600, easing: Easing.in(Easing.quad) }),
      ),
      -1,
    );
    pulse.value = withRepeat(withTiming(1, { duration: 1400, easing: Easing.out(Easing.ease) }), -1);
    return () => {
      clearInterval(id);
      cancelAnimation(bob);
      cancelAnimation(pulse);
    };
  }, [visible, bob, pulse]);

  const crateStyle = useAnimatedStyle(() => ({ transform: [{ translateY: -bob.value * 12 }] }));
  const ringStyle = useAnimatedStyle(() => ({
    opacity: 0.35 * (1 - pulse.value),
    transform: [{ scale: 1 + pulse.value * 0.9 }],
  }));

  return (
    <Modal visible={visible} transparent animationType="fade" statusBarTranslucent onRequestClose={() => {}}>
      <View style={styles.backdrop}>
        <Animated.View entering={FadeIn.duration(200)} style={styles.card}>
          <View style={styles.iconWrap}>
            <Animated.View style={[styles.ring, ringStyle]} />
            <Animated.View style={[styles.iconCircle, crateStyle]}>
              <Feather name="shopping-bag" size={34} color={colors.primary} />
            </Animated.View>
          </View>
          <Text variant="h3" align="center" style={styles.title}>
            Placing your order
          </Text>
          <View style={styles.stepBox}>
            <Animated.View key={step} entering={FadeInDown.duration(300)} exiting={FadeOutUp.duration(150)}>
              <Text variant="bodySmall" color={colors.textSecondary} align="center">
                {STEPS[step]}
              </Text>
            </Animated.View>
          </View>
          <BazaarLoader size={10} palette={[colors.primary, colors.accent, colors.primaryLight]} />
          <Text variant="caption" color={colors.textSecondary} align="center" style={styles.note}>
            Please don't close the app
          </Text>
        </Animated.View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(15,40,28,0.55)", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  card: {
    width: "100%",
    maxWidth: 340,
    backgroundColor: colors.surface,
    borderRadius: radius.card,
    paddingVertical: spacing.xl,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
  },
  iconWrap: { width: 96, height: 96, alignItems: "center", justifyContent: "center", marginBottom: spacing.md },
  ring: { position: "absolute", width: 72, height: 72, borderRadius: 36, backgroundColor: colors.primary },
  iconCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  title: { marginBottom: spacing.xs },
  stepBox: { minHeight: 36, justifyContent: "center", marginBottom: spacing.md },
  note: { marginTop: spacing.md },
});
