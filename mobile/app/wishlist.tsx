import React from "react";
import { useRouter, Stack } from "expo-router";
import { Screen } from "@/components/Screen";
import { EmptyState } from "@/components/EmptyState";
import { ProductGrid } from "@/components/ProductGrid";
import { productSummaryToCardData } from "@/components/ProductCard";
import { useWishlist } from "@/features/wishlist/useWishlist";

export default function WishlistScreen() {
  const router = useRouter();
  const { data, isLoading } = useWishlist();
  const products = (data?.items ?? []).map(productSummaryToCardData);

  return (
    <Screen edges={["bottom"]}>
      <Stack.Screen options={{ headerShown: true, title: "Wishlist" }} />
      <ProductGrid
        products={products}
        isLoading={isLoading}
        onPressProduct={(id) => router.push(`/product/${id}`)}
        ListEmptyComponent={
          <EmptyState
            icon="heart"
            title="Your wishlist is empty"
            message="Tap the heart on any product to save it here."
            actionLabel="Browse products"
            onAction={() => router.push("/(tabs)")}
          />
        }
      />
    </Screen>
  );
}
