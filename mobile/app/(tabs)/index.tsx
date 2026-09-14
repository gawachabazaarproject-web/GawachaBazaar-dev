import React, { useMemo, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { useQueryClient } from "@tanstack/react-query";
import { Feather } from "@expo/vector-icons";
import Animated, { FadeInDown, FadeInRight } from "react-native-reanimated";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { ProductCardData, productSummaryToCardData } from "@/components/ProductCard";
import { ProductCardSkeleton, Skeleton } from "@/components/Skeleton";
import { CART_BAR_CLEARANCE } from "@/components/CartBar";
import { ShopHeader } from "@/components/ShopHeader";
import { HorizontalProductCard } from "@/components/HorizontalProductCard";
import { PromoCarousel } from "@/components/home/PromoCarousel";
import { BrandStatement } from "@/components/home/BrandStatement";
import { CategoryPanel } from "@/components/home/CategoryPanel";
import { SectionHeading } from "@/components/home/SectionHeading";
import { ProductRail } from "@/components/home/ProductRail";
import { VillageStory } from "@/components/home/VillageStory";
import { ClosingCTA } from "@/components/home/ClosingCTA";
import { WholesaleToggle } from "@/components/home/WholesaleToggle";
import { WholesaleProductCard } from "@/components/home/WholesaleProductCard";
import { useCategories, useProducts } from "@/features/catalog/useCatalog";
import { useAddresses } from "@/features/address/useAddresses";
import { useWholesaleStore } from "@/store/wholesaleStore";
import { colors, radius, spacing } from "@/theme";

const HARVEST_SLUGS = ["ripe-tomatoes", "fresh-fenugreek", "green-peas", "chillies-coriander"];
const SPECIALTY_SLUGS = ["fresh-oranges", "toned-milk", "toor-dal"];

export default function HomeScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const { data: categories, isLoading: categoriesLoading } = useCategories();
  const { data: productsPages, isLoading: productsLoading } = useProducts({});
  const { data: addresses } = useAddresses();
  const mode = useWholesaleStore((s) => s.mode);
  const setMode = useWholesaleStore((s) => s.setMode);

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

  const goToProduct = (product: ProductCardData) => router.push(`/product/${product.id}`);

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
          onCartPress={() => router.push("/cart")}
        />

        <Pressable style={styles.searchBar} onPress={() => router.push("/(tabs)/search")}>
          <Feather name="search" size={16} color={colors.textMuted} />
          <Text variant="body" color={colors.textMuted} style={{ marginLeft: spacing.sm }} numberOfLines={1}>
            Search for atta, rice, milk...
          </Text>
        </Pressable>

        <View style={styles.carouselWrap}>
          <PromoCarousel onSlidePress={() => router.push("/(tabs)/categories")} />
        </View>

        <WholesaleToggle mode={mode} onChange={setMode} />
        {mode === "wholesale" ? (
          <View style={styles.wholesaleIntro}>
            <Text variant="eyebrow" color={colors.accentDark}>
              WHOLESALE
            </Text>
            <Text variant="h1" style={{ marginTop: spacing.sm }}>
              Bulk pricing
              <Text variant="script" color={colors.primary}>
                {" "}
                made simple.
              </Text>
            </Text>
            <Text variant="body" color={colors.textSecondary} style={{ marginTop: spacing.md }}>
              Pick a quantity for anything below and add it to a request - our team quotes it
              directly, nothing is charged until you accept.
            </Text>
            <Pressable onPress={() => router.push("/bulk/requests")} style={styles.wholesaleLink}>
              <Feather name="clock" size={14} color={colors.primary} />
              <Text variant="bodyMedium" color={colors.primary} style={{ marginLeft: spacing.xs }}>
                View your past requests
              </Text>
            </Pressable>
          </View>
        ) : null}

        {mode === "regular" ? <BrandStatement /> : null}

        {/* Shop by category */}
        <SectionHeading index="01 / 05" eyebrow="EXPLORE" title="Shop by" scriptSuffix="category." onSeeAll={() => router.push("/(tabs)/categories")} />
        {categoriesLoading ? (
          <View style={styles.categoryRow}>
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} width={168} height={226} borderRadius={0} />
            ))}
          </View>
        ) : (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.categoryRow}>
            {(categories ?? []).map((category, index) => (
              <Animated.View key={category.id} entering={FadeInRight.delay(index * 50).duration(280)}>
                <CategoryPanel
                  id={category.id}
                  slug={category.slug}
                  name={category.name}
                  index={index}
                  onPress={() => router.push(`/category/${category.id}`)}
                />
              </Animated.View>
            ))}
          </ScrollView>
        )}

        {/* Today's Market */}
        {productsLoading ? (
          <View style={styles.skeletonRail}>
            {[1, 2, 3].map((i) => (
              <View key={i} style={{ width: 158 }}>
                <ProductCardSkeleton />
              </View>
            ))}
          </View>
        ) : (
          <ProductRail
            index="02 / 05"
            eyebrow="TODAY'S MARKET"
            title="Morning"
            scriptSuffix="harvest."
            description="Picked at 4 AM, direct from Saoner mandis - here before it wilts."
            products={harvestProducts}
            onProductPress={goToProduct}
            onSeeAll={() => router.push("/(tabs)/categories")}
            cardWidth={mode === "wholesale" ? 190 : undefined}
            renderCard={
              mode === "wholesale"
                ? (product) => <WholesaleProductCard product={product} onPress={() => goToProduct(product)} />
                : undefined
            }
          />
        )}

        {mode === "regular" ? <VillageStory onPress={() => router.push("/(tabs)/categories")} /> : null}

        {/* Best sellers */}
        <ProductRail
          index="04 / 05"
          eyebrow="BEST SELLERS"
          title="Everyday"
          scriptSuffix="essentials."
          description="The staples Nagpur households reorder every week."
          products={restProducts}
          onProductPress={goToProduct}
          onSeeAll={() => router.push("/(tabs)/categories")}
          cardWidth={mode === "wholesale" ? 190 : undefined}
          renderCard={
            mode === "wholesale"
              ? (product) => <WholesaleProductCard product={product} onPress={() => goToProduct(product)} />
              : undefined
          }
        />

        {/* Vidarbha Regional Specialties */}
        {specialtyProducts.length > 0 ? (
          <View style={styles.specialties}>
            <SectionHeading
              index="05 / 05"
              eyebrow="VILLAGE SPECIALS"
              title="Vidarbha"
              scriptSuffix="specialties."
              description="GI-tagged and origin-authenticated, sourced straight from the growing belt."
            />
            {specialtyProducts.map((product, index) => (
              <Animated.View key={product.id} entering={FadeInDown.delay(index * 60).duration(280)}>
                {mode === "wholesale" ? (
                  <View style={styles.wholesaleSpecialtyItem}>
                    <WholesaleProductCard product={product} onPress={() => goToProduct(product)} />
                  </View>
                ) : (
                  <HorizontalProductCard product={product} onPress={() => goToProduct(product)} />
                )}
              </Animated.View>
            ))}
          </View>
        ) : null}

        <ClosingCTA onPress={() => router.push("/(tabs)/categories")} />
      </ScrollView>
    </Screen>
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
    borderRadius: radius.none,
    paddingHorizontal: spacing.md,
    height: 48,
  },
  carouselWrap: { marginTop: spacing.lg },
  categoryRow: { paddingHorizontal: spacing.base, gap: spacing.sm, flexDirection: "row" },
  skeletonRail: { flexDirection: "row", gap: spacing.md, paddingHorizontal: spacing.base, marginTop: spacing.xl },
  specialties: { marginTop: spacing.xl },
  wholesaleIntro: { paddingHorizontal: spacing.base, marginTop: spacing["2xl"], marginBottom: spacing["2xl"] },
  wholesaleLink: { flexDirection: "row", alignItems: "center", marginTop: spacing.xl },
  wholesaleSpecialtyItem: { paddingHorizontal: spacing.base, marginBottom: spacing.base, maxWidth: 220 },
});
