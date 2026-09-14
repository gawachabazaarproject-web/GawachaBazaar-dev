import React from "react";
import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { Screen } from "@/components/Screen";
import { ProductGrid } from "@/components/ProductGrid";
import { EmptyState } from "@/components/EmptyState";
import { productSummaryToCardData } from "@/components/ProductCard";
import { useCategory, useProducts } from "@/features/catalog/useCatalog";

export default function CategoryProductsScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const categoryId = Number(id);
  const router = useRouter();
  const { data: category } = useCategory(categoryId);
  const { data, isLoading, isFetchingNextPage, fetchNextPage, hasNextPage } = useProducts({ categoryId });

  const products = data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <Screen edges={["top", "bottom"]}>
      <Stack.Screen options={{ headerShown: true, title: category?.name ?? "Category" }} />
      <ProductGrid
        products={products.map(productSummaryToCardData)}
        isLoading={isLoading}
        isFetchingNextPage={isFetchingNextPage}
        onEndReached={() => hasNextPage && fetchNextPage()}
        onPressProduct={(productId) => router.push(`/product/${productId}`)}
        ListEmptyComponent={
          <EmptyState icon="box" title="No products here yet" message="Check back soon for new arrivals in this category." />
        }
      />
    </Screen>
  );
}
