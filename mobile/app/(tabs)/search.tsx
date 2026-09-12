import React, { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { TextField } from "@/components/TextField";
import { ProductGrid } from "@/components/ProductGrid";
import { EmptyState } from "@/components/EmptyState";
import { productSummaryToCardData } from "@/components/ProductCard";
import { useProducts } from "@/features/catalog/useCatalog";
import { useRecentSearches } from "@/features/catalog/useRecentSearches";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { colors, spacing } from "@/theme";

export default function SearchScreen() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query.trim(), 350);
  const { recent, addRecent, clearRecent } = useRecentSearches();

  const searchEnabled = debouncedQuery.length > 0;
  const { data, isLoading, isFetchingNextPage, fetchNextPage, hasNextPage } = useProducts(
    searchEnabled ? { q: debouncedQuery } : { q: undefined },
  );
  const products = data?.pages.flatMap((p) => p.items) ?? [];

  const handleSubmit = () => {
    if (query.trim().length > 0) addRecent(query.trim());
  };

  return (
    <Screen edges={["top"]}>
      <View style={styles.header}>
        <TextField
          placeholder="Search for atta, rice, milk..."
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={handleSubmit}
          autoFocus
          returnKeyType="search"
          autoCapitalize="none"
        />
      </View>

      {!searchEnabled ? (
        recent.length > 0 ? (
          <View style={styles.recentSection}>
            <View style={styles.recentHeader}>
              <Text variant="h3">Recent searches</Text>
              <Pressable onPress={clearRecent}>
                <Text variant="bodySmall" color={colors.primary}>
                  Clear
                </Text>
              </Pressable>
            </View>
            <View style={styles.recentList}>
              {recent.map((term) => (
                <Pressable key={term} style={styles.recentChip} onPress={() => setQuery(term)}>
                  <Feather name="clock" size={13} color={colors.textSecondary} />
                  <Text variant="bodySmall" style={{ marginLeft: spacing.xs }}>
                    {term}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
        ) : (
          <EmptyState icon="search" title="Search GawachaBazaar" message="Find groceries by name - try 'rice' or 'milk'." />
        )
      ) : (
        <ProductGrid
          products={products.map(productSummaryToCardData)}
          isLoading={isLoading}
          isFetchingNextPage={isFetchingNextPage}
          onEndReached={() => hasNextPage && fetchNextPage()}
          onPressProduct={(id) => router.push(`/product/${id}`)}
          ListEmptyComponent={
            <EmptyState icon="frown" title="No products found" message={`We couldn't find anything for "${debouncedQuery}". Try another search.`} />
          }
        />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { padding: spacing.base, paddingBottom: spacing.sm },
  recentSection: { paddingHorizontal: spacing.base },
  recentHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md },
  recentList: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  recentChip: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
});
