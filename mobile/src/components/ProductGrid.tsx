import React from "react";
import { ActivityIndicator, FlatList, StyleSheet, View } from "react-native";
import { ProductCard, ProductCardData } from "./ProductCard";
import { ProductCardSkeleton } from "./Skeleton";
import { CART_BAR_CLEARANCE } from "./CartBar";
import { colors, spacing } from "@/theme";

export interface ProductGridProps {
  products: ProductCardData[];
  isLoading: boolean;
  isFetchingNextPage?: boolean;
  onEndReached?: () => void;
  onPressProduct: (id: number) => void;
  ListEmptyComponent?: React.ReactElement;
  ListHeaderComponent?: React.ReactElement;
  ListFooterComponent?: React.ReactElement | null;
}

/** Two-column virtualized product grid shared by Category and Search
 * results - FlatList (not a manual ScrollView+flexWrap) so long catalogs
 * stay smooth and support infinite scroll. */
export function ProductGrid({
  products,
  isLoading,
  isFetchingNextPage,
  onEndReached,
  onPressProduct,
  ListEmptyComponent,
  ListHeaderComponent,
  ListFooterComponent,
}: ProductGridProps) {
  if (isLoading) {
    return (
      <View style={styles.skeletonGrid}>
        {[1, 2, 3, 4].map((i) => (
          <View key={i} style={styles.skeletonColumn}>
            <ProductCardSkeleton />
          </View>
        ))}
      </View>
    );
  }

  return (
    <FlatList
      data={products}
      keyExtractor={(item) => String(item.id)}
      numColumns={2}
      columnWrapperStyle={styles.row}
      contentContainerStyle={styles.content}
      renderItem={({ item, index }) => (
        <View style={styles.column}>
          <ProductCard product={item} onPress={() => onPressProduct(item.id)} index={index % 8} />
        </View>
      )}
      onEndReachedThreshold={0.4}
      onEndReached={onEndReached}
      ListHeaderComponent={ListHeaderComponent}
      ListEmptyComponent={ListEmptyComponent}
      ListFooterComponent={
        <>
          {ListFooterComponent ?? null}
          {isFetchingNextPage ? (
            <View style={styles.footer}>
              <ActivityIndicator color={colors.primary} />
            </View>
          ) : null}
        </>
      }
      showsVerticalScrollIndicator={false}
    />
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.base, paddingBottom: spacing.base + CART_BAR_CLEARANCE, flexGrow: 1 },
  row: { gap: spacing.md },
  column: { flex: 1, marginBottom: spacing.md },
  skeletonGrid: { flexDirection: "row", flexWrap: "wrap", padding: spacing.base, gap: spacing.md },
  skeletonColumn: { width: "47%" },
  footer: { paddingVertical: spacing.lg },
});
