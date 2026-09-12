import React, { useMemo, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { useQueryClient } from "@tanstack/react-query";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { ProductCard, productSummaryToCardData } from "@/components/ProductCard";
import { ProductCardSkeleton, Skeleton } from "@/components/Skeleton";
import { useCategories, useProducts } from "@/features/catalog/useCatalog";
import { useAddresses } from "@/features/address/useAddresses";
import { useOrders } from "@/features/orders/useOrders";
import { colors, radius, spacing } from "@/theme";

export default function HomeScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const { data: categories, isLoading: categoriesLoading } = useCategories();
  const { data: productsPages, isLoading: productsLoading } = useProducts({});
  const { data: addresses } = useAddresses();
  const { data: ordersPages } = useOrders();

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["categories"] }),
      queryClient.invalidateQueries({ queryKey: ["products"] }),
      queryClient.invalidateQueries({ queryKey: ["addresses"] }),
      queryClient.invalidateQueries({ queryKey: ["orders"] }),
    ]);
    setRefreshing(false);
  };

  const defaultAddress = addresses?.find((a) => a.is_default) ?? addresses?.[0];
  const products = productsPages?.pages.flatMap((p) => p.items) ?? [];

  const buyAgainProducts = useMemo(() => {
    const orders = ordersPages?.pages.flatMap((p) => p.items) ?? [];
    // Home only needs a light signal, not full order detail - real
    // "buy again" (with prices/variants) happens from Order Details,
    // where full items are already fetched. This just surfaces recent
    // order NUMBERS as a quick jump-back-in shortcut.
    return orders.slice(0, 3);
  }, [ordersPages]);

  return (
    <Screen edges={["top"]}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor={colors.primary} />}
      >
        {/* Delivery location */}
        <Pressable style={styles.locationRow} onPress={() => router.push("/address")}>
          <Feather name="map-pin" size={16} color={colors.primary} />
          <View style={styles.locationText}>
            <Text variant="caption" color={colors.textSecondary}>
              Delivering to
            </Text>
            <Text variant="bodyMedium" numberOfLines={1}>
              {defaultAddress ? `${defaultAddress.label} - ${defaultAddress.city}` : "Add an address"}
            </Text>
          </View>
          <Feather name="chevron-down" size={16} color={colors.textSecondary} />
        </Pressable>

        {/* Search entry point */}
        <Pressable style={styles.searchBar} onPress={() => router.push("/(tabs)/search")}>
          <Feather name="search" size={18} color={colors.textMuted} />
          <Text variant="body" color={colors.textMuted} style={{ marginLeft: spacing.sm }}>
            Search for atta, rice, milk...
          </Text>
        </Pressable>

        {/* Hero - restrained, single message, never dominating the screen */}
        <View style={styles.hero}>
          <Text variant="h2" color={colors.textInverse}>
            Farm-fresh groceries,{"\n"}delivered to your door.
          </Text>
        </View>

        {/* Categories */}
        <SectionHeader title="Shop by category" onSeeAll={() => router.push("/(tabs)/categories")} />
        {categoriesLoading ? (
          <View style={styles.categoryRow}>
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} width={64} height={64} borderRadius={32} />
            ))}
          </View>
        ) : (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.categoryRow}>
            {(categories ?? []).map((category) => (
              <Pressable
                key={category.id}
                style={styles.categoryItem}
                onPress={() => router.push(`/category/${category.id}`)}
              >
                <View style={styles.categoryCircle}>
                  <Text variant="h3" color={colors.primary}>
                    {category.name.charAt(0).toUpperCase()}
                  </Text>
                </View>
                <Text variant="caption" numberOfLines={1} style={styles.categoryLabel}>
                  {category.name}
                </Text>
              </Pressable>
            ))}
          </ScrollView>
        )}

        {/* Buy again */}
        {buyAgainProducts.length > 0 ? (
          <>
            <SectionHeader title="Buy again" onSeeAll={() => router.push("/(tabs)/orders")} />
            <View style={styles.buyAgainRow}>
              {buyAgainProducts.map((order) => (
                <Pressable key={order.id} style={styles.buyAgainCard} onPress={() => router.push(`/order/${order.id}`)}>
                  <Feather name="repeat" size={16} color={colors.primary} />
                  <Text variant="bodySmall" numberOfLines={1} style={{ marginTop: spacing.xs }}>
                    Order {order.order_number}
                  </Text>
                </Pressable>
              ))}
            </View>
          </>
        ) : null}

        {/* Products */}
        <SectionHeader title="Shop groceries" />
        <View style={styles.grid}>
          {productsLoading
            ? [1, 2, 3, 4].map((i) => (
                <View key={i} style={styles.gridItem}>
                  <ProductCardSkeleton />
                </View>
              ))
            : products.map((product) => (
                <View key={product.id} style={styles.gridItem}>
                  <ProductCard
                    product={productSummaryToCardData(product)}
                    onPress={() => router.push(`/product/${product.id}`)}
                  />
                </View>
              ))}
        </View>
      </ScrollView>
    </Screen>
  );
}

function SectionHeader({ title, onSeeAll }: { title: string; onSeeAll?: () => void }) {
  return (
    <View style={styles.sectionHeader}>
      <Text variant="h2">{title}</Text>
      {onSeeAll ? (
        <Pressable onPress={onSeeAll}>
          <Text variant="bodyMedium" color={colors.primary}>
            See all
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  scrollContent: { paddingBottom: spacing["4xl"] },
  locationRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.base,
    paddingTop: spacing.sm,
    gap: spacing.sm,
  },
  locationText: { flex: 1 },
  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: spacing.base,
    marginTop: spacing.base,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
  },
  hero: {
    margin: spacing.base,
    padding: spacing.xl,
    borderRadius: radius.xl,
    backgroundColor: colors.primary,
    minHeight: 120,
    justifyContent: "center",
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.base,
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
  categoryRow: { paddingHorizontal: spacing.base, gap: spacing.lg, flexDirection: "row" },
  categoryItem: { alignItems: "center", width: 68 },
  categoryCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.xs,
  },
  categoryLabel: { textAlign: "center" },
  buyAgainRow: { flexDirection: "row", paddingHorizontal: spacing.base, gap: spacing.md },
  buyAgainCard: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  grid: { flexDirection: "row", flexWrap: "wrap", paddingHorizontal: spacing.base, gap: spacing.md },
  gridItem: { width: "47%" },
});
