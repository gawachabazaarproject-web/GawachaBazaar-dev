import React from "react";
import { Pressable, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useWishlistToggle } from "@/features/wishlist/useWishlist";
import { colors } from "@/theme";

/** Round heart button that adds/removes a product from the wishlist. */
export function WishlistButton({ productId, size = 18 }: { productId: number; size?: number }) {
  const { liked, toggle } = useWishlistToggle(productId);
  return (
    <Pressable
      onPress={toggle}
      hitSlop={8}
      style={[styles.button, { width: size + 16, height: size + 16, borderRadius: (size + 16) / 2 }]}
      accessibilityRole="button"
      accessibilityLabel={liked ? "Remove from wishlist" : "Add to wishlist"}
    >
      <Ionicons name={liked ? "heart" : "heart-outline"} size={size} color={liked ? "#E0245E" : colors.textSecondary} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    backgroundColor: "rgba(255,255,255,0.92)",
    alignItems: "center",
    justifyContent: "center",
  },
});
