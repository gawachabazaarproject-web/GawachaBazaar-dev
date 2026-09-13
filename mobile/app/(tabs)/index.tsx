import React, { useMemo, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { useQueryClient } from "@tanstack/react-query";
import { Feather } from "@expo/vector-icons";
import Animated, { FadeInDown, FadeInRight, FadeInUp } from "react-native-reanimated";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { ProductCard, ProductCardData, productSummaryToCardData } from "@/components/ProductCard";
import { ProductCardSkeleton, Skeleton } from "@/components/Skeleton";
import { CategoryTile } from "@/components/CategoryTile";
import { PressableScale } from "@/components/PressableScale";
import { CART_BAR_CLEARANCE } from "@/components/CartBar";
import { ShopHeader } from "@/components/ShopHeader";
import { HorizontalProductCard } from "@/components/HorizontalProductCard";
import { ExclusiveBanner } from "@/components/home/ExclusiveBanner";
import { TrustFeatureStrip } from "@/components/home/TrustFeatureStrip";
import { FreshnessSectionHeader } from "@/components/home/FreshnessSectionHeader";
import { BrandPromiseCard } from "@/components/home/BrandPromiseCard";
import { useCategories, useProducts } from "@/features/catalog/useCatalog";
import { useAddresses } from "@/features/address/useAddresses";
import { colors, radius, shadows, spacing } from "@/theme";

const HARVEST_SLUGS = ["ripe-tomatoes", "fresh-fenugreek", "green-peas", "chillies-coriander"];
const SPECIALTY_SLUGS = ["fresh-oranges", "toned-milk", "toor-dal"];

export default function HomeScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const { data: categories, isLoading: categoriesLoading } = useCategories();
  const { data: productsPages, isLoading: productsLoading } = useProducts({});
  const { data: addresses } = useAddresses();

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["categories"] }),
      queryClient.invalidateQueries({ queryKey: ["products"] }),
      queryClient.invalidateQueries({ queryKey: ["addresses"] }),
    ]);
    setRefreshing(false);
  };

  const defaultAddress = addresses?.find((a) => a.is_default) ?? addresses?.[0];
  const allProducts = productsPages?.pages.flatMap((p) => p.items) ?? [];

  const { harvestProducts, specialtyProducts, restProducts } = useMemo(() => {
    const cards: ProductCardData[] = allProducts.map(productSummaryToCardData);
    const bySlug = new Map(cards.map((c) => [c.slug, c]));
    const harvest = HARVEST_SLUGS.map((s) => bySlug.get(s)).filter((c): c is ProductCardData => !!c);
    const specialty = SPECIALTY_SLUGS.map((s) => bySlug.get(s)).filter((c): c is ProductCardData => !!c);
    const featuredIds = new Set([...harvest, ...specialty].map((c) => c.id));
    const rest = cards.filter((c) => !featuredIds.has(c.id));
    return { harvestProducts: harvest, specialtyProducts: specialty, restProducts: rest };
  }, [allProducts]);

  return (
    <Screen edges={["top"]}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor={colors.primary} />}
      >
        <ShopHeader
          locationLabel={defaultAddress ? `${defaultAddress.label} - ${defaultAddress.city} (${defaultAddress.postal_code})` : "Add an address"}
          onLocationPress={() => router.push("/address")}
          onAccountPress={() => router.push("/(tabs)/account")}
        />

        <Pressable style={styles.searchBar} onPress={() => router.push("/(tabs)/search")}>
          <Feather name="search" size={16} color={colors.textMuted} />
          <Text variant="body" color={colors.textMuted} style={{ marginLeft: spacing.sm }} numberOfLines={1}>
            Search for atta, rice, milk...
          </Text>
        </Pressable>

        <Animated.View entering={FadeInUp.duration(300)}>
          <ExclusiveBanner />
        </Animated.View>

        <TrustFeatureStrip />

        {/* Categories */}
        <SectionHeader title="Shop by category" subtitle="Assorted by freshness zones" onSeeAll={() => router.push("/(tabs)/categories")} />
        {categoriesLoading ? (
          <View style={styles.categoryRow}>
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} width={56} height={56} borderRadius={28} />
            ))}
          </View>
        ) : (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.categoryRow}>
            {(categories ?? []).map((category, index) => (
              <Animated.View key={category.id} entering={FadeInRight.delay(index * 50).duration(280)}>
                <PressableScale style={styles.categoryItem} onPress={() => router.push(`/category/${category.id}`)}>
                  <CategoryTile slug={category.slug} size={56} />
                  <Text variant="caption" numberOfLines={1} style={styles.categoryLabel}>
                    {category.name}
                  </Text>
                </PressableScale>
              </Animated.View>
            ))}
          </ScrollView>
        )}

        {/* Today's Morning Harvest */}
        {productsLoading ? (
          <>
            <FreshnessSectionHeader />
            <View style={styles.grid}>
              {[1, 2, 3, 4].map((i) => (
                <View key={i} style={styles.gridItem}>
                  <ProductCardSkeleton />
                </View>
              ))}
            </View>
          </>
        ) : harvestProducts.length > 0 ? (
          <>
            <FreshnessSectionHeader />
            <View style={styles.grid}>
              {harvestProducts.map((product, index) => (
                <View key={product.id} style={styles.gridItem}>
                  <ProductCard product={product} onPress={() => router.push(`/product/${product.id}`)} index={index} />
                </View>
              ))}
            </View>
          </>
        ) : null}

        {/* Rest of the catalog */}
        {restProducts.length > 0 ? (
          <>
            <SectionHeader title="Shop groceries" />
            <View style={styles.grid}>
              {restProducts.map((product, index) => (
                <View key={product.id} style={styles.gridItem}>
                  <ProductCard product={product} onPress={() => router.push(`/product/${product.id}`)} index={index} />
                </View>
              ))}
            </View>
          </>
        ) : null}

        {/* Vidarbha Regional Specialties */}
        {specialtyProducts.length > 0 ? (
          <>
            <SectionHeader title="Vidarbha Regional Specialties" subtitle="GI-tagged & origin authenticated" />
            {specialtyProducts.map((product, index) => (
              <Animated.View key={product.id} entering={FadeInDown.delay(index * 60).duration(280)}>
                <HorizontalProductCard product={product} onPress={() => router.push(`/product/${product.id}`)} />
              </Animated.View>
            ))}
          </>
        ) : null}

        <BrandPromiseCard />
      </ScrollView>
    </Screen>
  );
}

function SectionHeader({ title, subtitle, onSeeAll }: { title: string; subtitle?: string; onSeeAll?: () => void }) {
  return (
    <View style={styles.sectionHeader}>
      <View style={{ flex: 1 }}>
        <Text variant="h2">{title}</Text>
        {subtitle ? (
          <Text variant="caption" color={colors.textSecondary} style={{ marginTop: 2 }}>
            {subtitle}
          </Text>
        ) : null}
      </View>
      {onSeeAll ? (
        <Pressable onPress={onSeeAll} style={styles.seeAll}>
          <Text variant="bodySmall" color={colors.primary}>
            View All
          </Text>
          <Feather name="arrow-right" size={12} color={colors.primary} />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  scrollContent: { paddingBottom: spacing.xl + CART_BAR_CLEARANCE },
  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: spacing.base,
    marginTop: spacing.sm,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.divider,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    height: 48,
    ...shadows.card,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    paddingHorizontal: spacing.base,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  seeAll: { flexDirection: "row", alignItems: "center", gap: 4 },
  categoryRow: { paddingHorizontal: spacing.base, gap: spacing.lg, flexDirection: "row" },
  categoryItem: { alignItems: "center", width: 64 },
  categoryLabel: { textAlign: "center", marginTop: spacing.sm },
  grid: { flexDirection: "row", flexWrap: "wrap", paddingHorizontal: spacing.base, gap: spacing.sm },
  gridItem: { width: "47%" },
});
