import React, { useEffect } from "react";
import { StyleSheet, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import Animated, { useSharedValue, withSequence, withSpring, useAnimatedStyle } from "react-native-reanimated";
import * as Haptics from "expo-haptics";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { colors, spacing, springs } from "@/theme";

/**
 * Bulk request submitted - a single tasteful confirmation moment (same
 * pattern as checkout/success.tsx). Deliberately does not show a total or
 * an ETA: nothing has been priced or scheduled yet, only requested.
 */
export default function BulkRequestSuccessScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const scale = useSharedValue(0.6);
  useEffect(() => {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    scale.value = withSequence(withSpring(1.08, springs.gentle), withSpring(1, springs.snappy));
  }, [scale]);
  const animatedStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));

  return (
    <Screen>
      <View style={styles.content}>
        <Animated.View style={[styles.iconCircle, animatedStyle]}>
          <Feather name="check" size={40} color={colors.textInverse} />
        </Animated.View>

        <Text variant="h1" align="center" style={styles.title}>
          Request sent
        </Text>
        <Text variant="body" color={colors.textSecondary} align="center" style={styles.subtitle}>
          Our team will review your bulk request and send you a quote - you&apos;ll be able to
          review pricing before anything is charged.
        </Text>

        <View style={styles.actions}>
          <Button
            label="Track this request"
            onPress={() => router.replace({ pathname: "/bulk/[id]", params: { id: String(id) } })}
            fullWidth
            size="lg"
          />
          <Button
            label="Continue shopping"
            variant="ghost"
            onPress={() => router.replace("/(tabs)")}
            style={{ marginTop: spacing.sm }}
          />
        </View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  iconCircle: {
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: colors.success,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.xl,
  },
  title: { marginBottom: spacing.xs },
  subtitle: { marginBottom: spacing.xl, maxWidth: 300 },
  actions: { width: "100%" },
});
