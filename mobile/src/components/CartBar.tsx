import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import Animated, { FadeInDown, FadeOutDown } from "react-native-reanimated";
import { Feather } from "@expo/vector-icons";
import { useRouter, useSegments } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Text } from "./Text";
import { useCart } from "@/features/cart/useCart";
import { useAuthStore } from "@/store/authStore";
import { formatMoney } from "@/utils/money";
import { colors, radius, shadows, spacing } from "@/theme";

const TAB_BAR_CONTENT_HEIGHT = 64;

/** Extra bottom padding scrollable screens should add so their last row
 * never ends up hidden behind the floating CartBar (tab bar height + bar
 * height + a safety margin covering the tallest realistic safe-area
 * inset). Import this instead of guessing a magic number per screen. */
export const CART_BAR_CLEARANCE = TAB_BAR_CONTENT_HEIGHT + 56 + 60;

/**
 * Persistent floating checkout bar (see DESIGN.md "Floating Bottom
 * Checkout Bar"): appears the moment the cart has items, disappears the
 * moment it's empty. Rendered once at the root so it floats above every
 * screen, not just the 5 main tabs - hidden only on the cart/checkout
 * screens themselves, where it would be redundant.
 */
export function CartBar() {
  const router = useRouter();
  const segments = useSegments();
  const insets = useSafeAreaInsets();
  const authStatus = useAuthStore((s) => s.status);
  const { data: cart } = useCart(authStatus === "authenticated");

  const inTabs = segments[0] === "(tabs)";
  // Hidden on any screen that already has its own bottom action bar -
  // cart/checkout show their own summary/pay bar, and product detail has
  // its own Add-to-cart footer; floating this bar on top of those would
  // stack two bottom bars on each other.
  const rootSegment = segments[0];
  const hiddenOnScreen = rootSegment === "cart" || rootSegment === "checkout" || rootSegment === "product";

  const itemCount = cart?.items.reduce((sum, i) => sum + Math.round(Number.parseFloat(i.quantity)), 0) ?? 0;
  if (!cart || itemCount === 0 || hiddenOnScreen) return null;

  const bottomOffset = inTabs ? TAB_BAR_CONTENT_HEIGHT + insets.bottom : insets.bottom + spacing.base;

  return (
    <Animated.View
      entering={FadeInDown.duration(220)}
      exiting={FadeOutDown.duration(180)}
      style={[styles.wrap, { bottom: bottomOffset }]}
      pointerEvents="box-none"
    >
      <Pressable style={styles.bar} onPress={() => router.push("/cart")} accessibilityRole="button" accessibilityLabel="View cart">
        <View style={styles.left}>
          <Text variant="label" color={colors.primaryLight}>
            {itemCount} {itemCount === 1 ? "ITEM" : "ITEMS"}
          </Text>
          <Text variant="price" color={colors.textInverse}>
            {formatMoney(cart.total_amount ?? "0", cart.currency ?? "INR")}
          </Text>
        </View>
        <View style={styles.right}>
          <Text variant="bodyMedium" color={colors.textInverse}>
            View Cart
          </Text>
          <View style={styles.ctaPill}>
            <Feather name="arrow-right" size={15} color={colors.textOnAccent} />
          </View>
        </View>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: "absolute", left: 0, right: 0, paddingHorizontal: spacing.md },
  bar: {
    height: 56,
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.primaryDark,
    paddingHorizontal: spacing.base,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    ...shadows.raised,
  },
  left: { justifyContent: "center", gap: 2 },
  right: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  ctaPill: {
    width: 28,
    height: 28,
    borderRadius: radius.pill,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
});
