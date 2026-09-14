import React, { useMemo, useState } from "react";
import { Pressable, StyleSheet, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { ShopHeader } from "@/components/ShopHeader";
import { ProductGrid } from "@/components/ProductGrid";
import { EmptyState } from "@/components/EmptyState";
import { FilterChip } from "@/components/FilterChip";
import { FreshnessStoryCard } from "@/components/FreshnessStoryCard";
import { RecommendationRail } from "@/components/RecommendationRail";
import { MiniProductTile } from "@/components/MiniProductTile";
import { productSummaryToCardData } from "@/components/ProductCard";
import { useAllProducts, useProducts } from "@/features/catalog/useCatalog";
import { useAddresses } from "@/features/address/useAddresses";
import { useRecentSearches } from "@/features/catalog/useRecentSearches";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { RELATED_PRODUCTS, DEFAULT_QUICK_SEARCH_TERMS } from "@/utils/relatedProducts";
import { colors, radius, shadows, spacing, typography } from "@/theme";

export default function SearchScreen() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query.trim(), 350);
  const { recent, addRecent, clearRecent } = useRecentSearches();
  const { data: addresses } = useAddresses();

  const searchEnabled = debouncedQuery.length > 0;
  const { data, isLoading, isFetchingNextPage, fetchNextPage, hasNextPage } = useProducts(
    searchEnabled ? { q: debouncedQuery } : { q: undefined },
  );
  // Full catalog, fetched once, purely to resolve "Pairs with X" from
  // real product data - same client-side-filter pattern the Home screen
  // already uses for its featured rails.
  const { data: allData } = useAllProducts();

  const products = data?.pages.flatMap((p) => p.items) ?? [];
  const allProducts = allData?.items ?? [];

  const defaultAddress = addresses?.find((a) => a.is_default) ?? addresses?.[0];

  const relatedProducts = useMemo(() => {
    if (products.length === 0) return [];
    const bySlug = new Map(allProducts.map((p) => [p.slug, p]));
    const relatedSlugs = RELATED_PRODUCTS[products[0].slug] ?? [];
    return relatedSlugs
      .map((s) => bySlug.get(s))
      .filter((p): p is NonNullable<typeof p> => !!p)
      .map(productSummaryToCardData);
  }, [products, allProducts]);

  const handleSubmit = () => {
    if (query.trim().length > 0) addRecent(query.trim());
  };

  const handleQuickTerm = (term: string) => {
    setQuery(term);
    addRecent(term);
  };

  return (
    <Screen edges={["top"]}>
      <ShopHeader
        locationLabel={defaultAddress ? `${defaultAddress.label} - ${defaultAddress.city}` : "Add an address"}
        onLocationPress={() => router.push("/address")}
        onAccountPress={() => router.push("/(tabs)/account")}
      />

      <View style={styles.searchRow}>
        <View style={styles.searchField}>
          <Feather name="search" size={16} color={colors.textMuted} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search for atta, rice, milk..."
            placeholderTextColor={colors.textMuted}
            value={query}
            onChangeText={setQuery}
            onSubmitEditing={handleSubmit}
            returnKeyType="search"
            autoCapitalize="none"
            autoFocus
          />
          {query.length > 0 ? (
            <Pressable onPress={() => setQuery("")} hitSlop={8}>
              <Feather name="x" size={16} color={colors.textMuted} />
            </Pressable>
          ) : null}
        </View>
      </View>

      {searchEnabled ? (
        <View style={styles.chipRow}>
          {DEFAULT_QUICK_SEARCH_TERMS.map((term) => (
            <FilterChip key={term} label={term} selected={term.toLowerCase() === debouncedQuery.toLowerCase()} onPress={() => handleQuickTerm(term)} />
          ))}
        </View>
      ) : null}

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
        <>
          {!isLoading ? (
            <View style={styles.statusRow}>
              <View style={styles.statusDot} />
              <Text variant="bodySmall" color={colors.textSecondary} style={{ flex: 1 }}>
                Showing {products.length} farm fresh {products.length === 1 ? "pick" : "picks"} in Nagpur
              </Text>
            </View>
          ) : null}
          <ProductGrid
            products={products.map(productSummaryToCardData)}
            isLoading={isLoading}
            isFetchingNextPage={isFetchingNextPage}
            onEndReached={() => hasNextPage && fetchNextPage()}
            onPressProduct={(id) => router.push(`/product/${id}`)}
            ListEmptyComponent={
              <EmptyState icon="frown" title="No products found" message={`We couldn't find anything for "${debouncedQuery}". Try another search.`} />
            }
            ListFooterComponent={
              !isLoading && products.length > 0 ? (
                <>
                  <FreshnessStoryCard />
                  {relatedProducts.length > 0 ? (
                    <RecommendationRail title={`Pairs with ${products[0].name}`} subtitle="Daily tadka & chutney essentials">
                      {relatedProducts.map((p) => (
                        <MiniProductTile key={p.id} product={p} onPress={() => router.push(`/product/${p.id}`)} />
                      ))}
                    </RecommendationRail>
                  ) : null}
                </>
              ) : null
            }
          />
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  searchRow: { paddingHorizontal: spacing.base, marginTop: spacing.sm },
  searchField: {
    flexDirection: "row",
    alignItems: "center",
    height: 48,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.divider,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    ...shadows.card,
  },
  searchInput: { flex: 1, marginLeft: spacing.sm, ...typography.body, color: colors.textPrimary, padding: 0 },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    paddingHorizontal: spacing.base,
    marginTop: spacing.sm,
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.base,
    marginTop: spacing.sm,
  },
  statusDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.accent },
  recentSection: { paddingHorizontal: spacing.base, marginTop: spacing.base },
  recentHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md },
  recentList: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  recentChip: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.divider,
    borderRadius: 999,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
  },
});
