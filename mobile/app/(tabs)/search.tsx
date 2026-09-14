import React, { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, TextInput, View } from "react-native";
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
import { useAllProducts, useCategories, useProducts } from "@/features/catalog/useCatalog";
import { useAddresses } from "@/features/address/useAddresses";
import { useRecentSearches } from "@/features/catalog/useRecentSearches";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { RELATED_PRODUCTS, DEFAULT_QUICK_SEARCH_TERMS } from "@/utils/relatedProducts";
import { colors, radius, spacing, typography } from "@/theme";

export default function SearchScreen() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query.trim(), 350);
  const { recent, addRecent, clearRecent } = useRecentSearches();
  const { data: addresses } = useAddresses();
  const { data: categories } = useCategories();

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
        onCartPress={() => router.push("/cart")}
      />

      {!searchEnabled ? (
        <View style={styles.heroWrap}>
          <Text variant="eyebrow" color={colors.accentDark}>
            SEARCH
          </Text>
          <Text variant="displayL" style={styles.heroTitle}>
            What are you{"\n"}
            <Text variant="script" color={colors.primary}>
              looking for?
            </Text>
          </Text>
        </View>
      ) : null}

      <View style={[styles.searchRow, !searchEnabled && styles.searchRowHero]}>
        <View style={[styles.searchField, !searchEnabled && styles.searchFieldHero]}>
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
            <Pressable onPress={() => setQuery("")} hitSlop={8} accessibilityRole="button" accessibilityLabel="Clear search">
              <Feather name="x" size={16} color={colors.textMuted} />
            </Pressable>
          ) : null}
        </View>
      </View>

      {!searchEnabled ? (
        <ScrollView showsVerticalScrollIndicator={false}>
          <View style={styles.section}>
            <Text variant="eyebrow" color={colors.accentDark}>
              POPULAR SEARCHES
            </Text>
            <View style={styles.chipRow}>
              {DEFAULT_QUICK_SEARCH_TERMS.map((term) => (
                <FilterChip key={term} label={term} selected={false} onPress={() => handleQuickTerm(term)} />
              ))}
            </View>
          </View>

          {recent.length > 0 ? (
            <View style={styles.section}>
              <View style={styles.recentHeader}>
                <Text variant="eyebrow" color={colors.accentDark}>
                  RECENT
                </Text>
                <Pressable onPress={clearRecent} accessibilityRole="button" accessibilityLabel="Clear recent searches">
                  <Text variant="bodySmall" color={colors.primary}>
                    Clear
                  </Text>
                </Pressable>
              </View>
              {recent.map((term, i) => (
                <Pressable
                  key={term}
                  style={[styles.recentRow, i === recent.length - 1 && styles.recentRowLast]}
                  onPress={() => setQuery(term)}
                >
                  <Feather name="clock" size={14} color={colors.textSecondary} />
                  <Text variant="body" style={{ marginLeft: spacing.sm }}>
                    {term}
                  </Text>
                  <Feather name="arrow-up-right" size={14} color={colors.textMuted} style={{ marginLeft: "auto" }} />
                </Pressable>
              ))}
            </View>
          ) : null}

          {categories && categories.length > 0 ? (
            <View style={styles.section}>
              <Text variant="eyebrow" color={colors.accentDark}>
                BROWSE BY CATEGORY
              </Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.categoryRow}>
                {categories.map((category) => (
                  <Pressable key={category.id} style={styles.categoryChip} onPress={() => router.push(`/category/${category.id}`)}>
                    <Text variant="bodySmall">{category.name}</Text>
                    <Feather name="arrow-up-right" size={12} color={colors.textSecondary} />
                  </Pressable>
                ))}
              </ScrollView>
            </View>
          ) : null}
        </ScrollView>
      ) : (
        <>
          {!isLoading ? (
            <View style={styles.resultsHeader}>
              <Text variant="eyebrow" color={colors.textMuted}>
                SEARCH RESULTS
              </Text>
              <Text variant="h2" style={styles.resultsTitle}>
                &quot;{debouncedQuery}&quot;
              </Text>
              <Text variant="caption" color={colors.textSecondary} style={styles.resultsMeta}>
                {products.length} {products.length === 1 ? "pick" : "picks"} found
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
  heroWrap: { paddingHorizontal: spacing.base, marginTop: spacing.xl },
  heroTitle: { marginTop: spacing.sm },
  searchRow: { paddingHorizontal: spacing.base, marginTop: spacing.sm },
  searchRowHero: { marginTop: spacing.xl },
  searchField: {
    flexDirection: "row",
    alignItems: "center",
    height: 48,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.divider,
    borderRadius: radius.none,
    paddingHorizontal: spacing.md,
  },
  searchFieldHero: { height: 56, borderColor: colors.textPrimary },
  searchInput: { flex: 1, marginLeft: spacing.sm, ...typography.body, color: colors.textPrimary, padding: 0 },
  section: { paddingHorizontal: spacing.base, marginTop: spacing["2xl"] },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.base },
  recentHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  recentRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderColor: colors.divider,
    marginTop: spacing.sm,
  },
  recentRowLast: { borderBottomWidth: 0 },
  categoryRow: { gap: spacing.sm, marginTop: spacing.base },
  categoryChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.divider,
    borderRadius: radius.none,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
  },
  resultsHeader: { paddingHorizontal: spacing.base, marginTop: spacing.lg, marginBottom: spacing.sm },
  resultsTitle: { marginTop: spacing.xs },
  resultsMeta: { marginTop: spacing.xs },
});
