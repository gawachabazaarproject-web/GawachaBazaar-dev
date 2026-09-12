import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import Animated, { FadeInDown, FadeOutDown } from "react-native-reanimated";
import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { Text } from "./Text";
import { useCart } from "@/features/cart/useCart";
import { formatMoney } from "@/utils/money";
import { colors, radius, shadows, spacing } from "@/theme";

/**
 * Persistent cart bar (brief §17/§25): appears the moment the cart has
 * items, disappears the moment it's empty. Lives above the tab bar, not
 * as a permanent tab itself.
 */
export function CartBar() {
  const router = useRouter();
  const { data: cart } = useCart();

  const itemCount = cart?.items.reduce((sum, i) => sum + Math.round(Number.parseFloat(i.quantity)), 0) ?? 0;
  if (!cart || itemCount === 0) return null;

  return (
    <Animated.View entering={FadeInDown.duration(220)} exiting={FadeOutDown.duration(180)} style={styles.wrap}>
      <Pressable style={styles.bar} onPress={() => router.push("/cart")} accessibilityRole="button" accessibilityLabel="View cart">
        <View style={styles.left}>
          <Feather name="shopping-cart" size={16} color={colors.textInverse} />
          <Text variant="bodyMedium" color={colors.textInverse}>
            {itemCount} {itemCount === 1 ? "item" : "items"}
          </Text>
        </View>
        <View style={styles.right}>
          <Text variant="bodyMedium" color={colors.textInverse}>
            {formatMoney(cart.total_amount ?? "0", cart.currency ?? "INR")}
          </Text>
          <Feather name="arrow-right" size={16} color={colors.textInverse} />
        </View>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: spacing.base, paddingBottom: spacing.sm },
  bar: {
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.base,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    ...shadows.raised,
  },
  left: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  right: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
});
