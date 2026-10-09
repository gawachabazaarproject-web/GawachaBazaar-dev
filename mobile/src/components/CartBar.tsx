import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import Animated, { FadeInDown, FadeOutDown } from "react-native-reanimated";
import { Feather } from "@expo/vector-icons";
import { useRouter, useSegments } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Text } from "./Text";
import { useCart } from "@/features/cart/useCart";
import { useAuthStore } from "@/store/authStore";
import { useWholesaleStore } from "@/store/wholesaleStore";
import { formatMoney } from "@/utils/money";
import { colors, radius, shadows, spacing } from "@/theme";

const TAB_BAR_CONTENT_HEIGHT = 64;
/** Product detail's Add-to-cart footer height excluding the bottom inset. */
const PRODUCT_FOOTER_HEIGHT = 68;

/** Extra bottom padding scrollable screens should add so their last row
 * never ends up hidden behind the floating CartBar (tab bar height + bar
 * height + a safety margin covering the tallest realistic safe-area
 * inset). Import this instead of guessing a magic number per screen. */
export const CART_BAR_CLEARANCE = TAB_BAR_CONTENT_HEIGHT + 56 + 76;

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
  const wholesaleMode = useWholesaleStore((s) => s.mode);
  const { data: cart } = useCart(authStatus === "authenticated");

  const inTabs = segments[0] === "(tabs)";
  // Hidden on cart/checkout (own summary/pay bar) and the Bazaar page (own
  // basket bar). Product
  // detail keeps its Add-to-cart footer, so the pill floats just above it.
  const rootSegment = segments[0];
  const hiddenOnScreen = rootSegment === "cart" || rootSegment === "checkout" || rootSegment === "bazaar";
  const onProduct = rootSegment === "product";

  const itemCount = cart?.items.reduce((sum, i) => sum + Math.round(Number.parseFloat(i.quantity)), 0) ?? 0;
  if (!cart || itemCount === 0 || hiddenOnScreen || wholesaleMode === "wholesale") return null;

  const bottomOffset = inTabs
    ? TAB_BAR_CONTENT_HEIGHT + insets.bottom + spacing.xs
    : onProduct
      ? PRODUCT_FOOTER_HEIGHT + insets.bottom + spacing.sm
      : insets.bottom + spacing.xl;

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
    borderRadius: radius.card,
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
