import React, { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import Animated, { FadeInDown } from "react-native-reanimated";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Skeleton } from "@/components/Skeleton";
import { ShopHeader } from "@/components/ShopHeader";
import { ProductCard, productSummaryToCardData } from "@/components/ProductCard";
import { FilterChip } from "@/components/FilterChip";
import { PressableScale } from "@/components/PressableScale";
import { EmptyState } from "@/components/EmptyState";
import { CART_BAR_CLEARANCE } from "@/components/CartBar";
import { useAllProducts, useCategories } from "@/features/catalog/useCatalog";
import { useAddresses } from "@/features/address/useAddresses";
import { CATEGORY_MARATHI, CATEGORY_ICONS, getDepartments, getCategoryStory } from "@/utils/categoryDepartments";
import { colors, radius, shadows, spacing } from "@/theme";
import { CategoryResponse } from "@/types/api";

export default function CategoriesScreen() {
  const router = useRouter();
  const { data: categories, isLoading: categoriesLoading } = useCategories();
  const { data: productsData, isLoading: productsLoading } = useAllProducts();
  const { data: addresses } = useAddresses();
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string | null>(null);

  const defaultAddress = addresses?.find((a) => a.is_default) ?? addresses?.[0];
  const allProducts = useMemo(() => productsData?.items ?? [], [productsData]);
  const productsBySlug = useMemo(() => new Map(allProducts.map((p) => [p.slug, p])), [allProducts]);

  const activeCategory = useMemo(() => {
    if (!categories || categories.length === 0) return null;
    return categories.find((c) => c.id === selectedCategoryId) ?? categories[0];
  }, [categories, selectedCategoryId]);

  const categoryProducts = useMemo(
    () => (activeCategory ? allProducts.filter((p) => p.category_id === activeCategory.id) : []),
    [allProducts, activeCategory],
  );

  const departments = activeCategory ? getDepartments(activeCategory.slug) : [];
  const selectedDepartment = departments.find((d) => d.id === selectedDepartmentId) ?? null;

  const visibleProducts = useMemo(() => {
    if (!selectedDepartment) return categoryProducts;
    const slugSet = new Set(selectedDepartment.productSlugs);
    return categoryProducts.filter((p) => slugSet.has(p.slug));
  }, [categoryProducts, selectedDepartment]);

  const totalDepartments = (categories ?? []).reduce((sum, c) => sum + getDepartments(c.slug).length, 0);

  const handleSelectCategory = (id: number) => {
    setSelectedCategoryId(id);
    setSelectedDepartmentId(null);
  };

  const isLoading = categoriesLoading || productsLoading || !activeCategory;

  return (
    <Screen edges={["top"]}>
      <ShopHeader
        locationLabel={defaultAddress ? `${defaultAddress.label} - ${defaultAddress.city}` : "Add an address"}
        onLocationPress={() => router.push("/address")}
        onAccountPress={() => router.push("/(tabs)/account")}
      />

      <Pressable style={styles.searchBar} onPress={() => router.push("/(tabs)/search")}>
        <Feather name="search" size={16} color={colors.textMuted} />
        <Text variant="body" color={colors.textMuted} style={styles.searchPlaceholder} numberOfLines={1}>
          Search all {totalDepartments || "..."} departments...
        </Text>
        <Feather name="mic" size={15} color={colors.textMuted} />
      </Pressable>

      {isLoading ? (
        <View style={styles.loadingWrap}>
          <Skeleton height={150} borderRadius={radius.md} style={{ marginBottom: spacing.lg }} />
          <View style={styles.deptGrid}>
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} height={150} borderRadius={radius.lg} style={styles.skeletonItem} />
            ))}
          </View>
        </View>
      ) : (
        <View style={styles.body}>
          <View style={styles.railBounds}>
            <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.railContent}>
              {categories!.map((category) => (
                <RailItem
                  key={category.id}
                  category={category}
                  count={allProducts.filter((p) => p.category_id === category.id).length}
                  active={category.id === activeCategory!.id}
                  onPress={() => handleSelectCategory(category.id)}
                />
              ))}
            </ScrollView>
          </View>

          <ScrollView showsVerticalScrollIndicator={false} style={styles.content} contentContainerStyle={styles.contentInner}>
            <CategoryHero category={activeCategory!} />

            <View style={styles.chipRow}>
              <FilterChip label={`All (${categoryProducts.length})`} selected={!selectedDepartment} onPress={() => setSelectedDepartmentId(null)} />
              {departments.map((dept) => (
                <FilterChip
                  key={dept.id}
                  label={dept.name}
                  selected={selectedDepartmentId === dept.id}
                  onPress={() => setSelectedDepartmentId((cur) => (cur === dept.id ? null : dept.id))}
                />
              ))}
            </View>

            {departments.length > 0 ? (
              <>
                <View style={styles.sectionHeader}>
                  <Text variant="h3" numberOfLines={1} style={styles.sectionHeaderTitle}>
                    Departments
                  </Text>
                  <Text variant="caption" color={colors.textSecondary} numberOfLines={1}>
                    {departments.length} {departments.length === 1 ? "SECTION" : "SECTIONS"}
                  </Text>
                </View>
                <View style={styles.deptGrid}>
                  {departments.map((dept, index) => {
                    const thumbSlug = dept.productSlugs.find((s) => productsBySlug.has(s));
                    const thumbUrl = thumbSlug ? productsBySlug.get(thumbSlug)?.primary_image_url : null;
                    return (
                      <DepartmentTile
                        key={dept.id}
                        name={dept.name}
                        marathiName={dept.marathiName}
                        count={dept.productSlugs.length}
                        imageUrl={thumbUrl ?? null}
                        index={index}
                        selected={selectedDepartmentId === dept.id}
                        onPress={() => setSelectedDepartmentId((cur) => (cur === dept.id ? null : dept.id))}
                      />
                    );
                  })}
                </View>
              </>
            ) : null}

            <View style={styles.sectionHeader}>
              <Text variant="h3" numberOfLines={1} style={styles.sectionHeaderTitle}>
                {selectedDepartment ? selectedDepartment.name : "All Products"}
              </Text>
              <Text variant="caption" color={colors.textSecondary} numberOfLines={1}>
                {visibleProducts.length} {visibleProducts.length === 1 ? "ITEM" : "ITEMS"}
              </Text>
            </View>
            {visibleProducts.length > 0 ? (
              <View style={styles.productGrid}>
                {visibleProducts.map((product, index) => (
                  <View key={product.id} style={styles.productGridItem}>
                    <ProductCard product={productSummaryToCardData(product)} onPress={() => router.push(`/product/${product.id}`)} index={index} />
                  </View>
                ))}
              </View>
            ) : (
              <EmptyState icon="box" title="No products here yet" message="Check back soon for new arrivals in this department." />
            )}

            <View style={styles.trustRow}>
              <Feather name="truck" size={14} color={colors.accent} />
              <Text variant="caption" color={colors.textSecondary} style={{ flex: 1 }}>
                100% traceable, direct from farmer - no middlemen cold storage.
              </Text>
            </View>
          </ScrollView>
        </View>
      )}
    </Screen>
  );
}

function RailItem({
  category,
  count,
  active,
  onPress,
}: {
  category: CategoryResponse;
  count: number;
  active: boolean;
  onPress: () => void;
}) {
  const icon = (CATEGORY_ICONS[category.slug] ?? "grid") as keyof typeof Feather.glyphMap;
  return (
    <PressableScale style={[styles.railItem, active && styles.railItemActive]} onPress={onPress} hapticStyle={null}>
      <View style={styles.railIconWrap}>
        <View style={[styles.railIconCircle, active && styles.railIconCircleActive]}>
          <Feather name={icon} size={18} color={active ? colors.primary : colors.textSecondary} />
        </View>
        {count > 0 ? (
          <View style={styles.railBadge}>
            <Text variant="label" color={colors.textOnAccent}>
              {count}
            </Text>
          </View>
        ) : null}
      </View>
      <Text variant="caption" color={active ? colors.primary : colors.textPrimary} align="center" numberOfLines={1} style={styles.railName}>
        {category.name}
      </Text>
      <Text variant="label" color={colors.textMuted} align="center" numberOfLines={1}>
        {CATEGORY_MARATHI[category.slug] ?? ""}
      </Text>
    </PressableScale>
  );
}

function CategoryHero({ category }: { category: CategoryResponse }) {
  return (
    <Animated.View entering={FadeInDown.duration(220)} style={styles.hero}>
      <View style={styles.heroTagRow}>
        <Feather name="award" size={11} color={colors.accent} />
        <Text variant="label" color={colors.accent}>
          VIDARBHA FARMER CLUSTERS
        </Text>
      </View>
      <Text variant="h3" color={colors.textInverse} style={styles.heroTitle}>
        {category.name}
      </Text>
      <Text variant="bodySmall" color={colors.primaryLight} style={styles.heroBody}>
        {getCategoryStory(category.slug)}
      </Text>
      <View style={styles.heroFooter}>
        <Feather name="clock" size={12} color={colors.primaryLight} />
        <Text variant="caption" color={colors.primaryLight} style={{ flex: 1 }}>
          Next dispatch from Saoner Mandi Hub: 18 mins
        </Text>
      </View>
    </Animated.View>
  );
}

function DepartmentTile({
  name,
  marathiName,
  count,
  imageUrl,
  index,
  selected,
  onPress,
}: {
  name: string;
  marathiName: string;
  count: number;
  imageUrl: string | null;
  index: number;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Animated.View entering={FadeInDown.delay(Math.min(index, 6) * 45).duration(260)} style={styles.deptCell}>
      <PressableScale style={[styles.deptCard, selected && styles.deptCardSelected]} onPress={onPress}>
        <Image source={imageUrl ?? undefined} style={styles.deptImage} contentFit="cover" transition={150} />
        <View style={styles.deptCountBadge}>
          <Text variant="label" color={colors.textInverse}>
            {count} {count === 1 ? "ITEM" : "ITEMS"}
          </Text>
        </View>
        <View style={styles.deptInfo}>
          <Text variant="bodyMedium" numberOfLines={1}>
            {name}
          </Text>
          <Text variant="caption" color={colors.textSecondary} numberOfLines={1}>
            {marathiName}
          </Text>
        </View>
      </PressableScale>
    </Animated.View>
  );
}

const RAIL_WIDTH = 76;

const styles = StyleSheet.create({
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
  searchPlaceholder: { marginLeft: spacing.sm, flex: 1 },
  loadingWrap: { padding: spacing.base },
  skeletonItem: { width: "47%" },
  body: { flex: 1, flexDirection: "row" },
  railBounds: { width: RAIL_WIDTH, flexGrow: 0, flexShrink: 0, flexBasis: RAIL_WIDTH, overflow: "hidden", backgroundColor: colors.background },
  railContent: { paddingVertical: spacing.md, paddingHorizontal: spacing.xs, gap: spacing.sm },
  railItem: { alignItems: "center", paddingVertical: spacing.sm, paddingHorizontal: 2, borderRadius: radius.md },
  railItemActive: { backgroundColor: colors.primaryLight },
  railIconWrap: { position: "relative" },
  railIconCircle: {
    width: 42,
    height: 42,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.divider,
  },
  railIconCircleActive: { backgroundColor: colors.surface, borderColor: colors.primary },
  railBadge: {
    position: "absolute",
    top: -4,
    right: -4,
    minWidth: 18,
    height: 18,
    borderRadius: radius.pill,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 3,
  },
  railName: { marginTop: spacing.xs },
  content: { flex: 1, minWidth: 0 },
  contentInner: { paddingVertical: spacing.base, paddingLeft: spacing.xs, paddingRight: spacing.sm, paddingBottom: spacing.xl + CART_BAR_CLEARANCE },
  hero: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    padding: spacing.md,
    ...shadows.raised,
  },
  heroTagRow: { flexDirection: "row", alignItems: "center", gap: 4 },
  heroTitle: { marginTop: spacing.xs },
  heroBody: { marginTop: spacing.xs },
  heroFooter: { flexDirection: "row", alignItems: "center", gap: spacing.xs, marginTop: spacing.md, paddingTop: spacing.sm, borderTopWidth: 1, borderTopColor: "rgba(255,255,255,0.12)" },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.base },
  sectionHeader: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", marginTop: spacing.lg, marginBottom: spacing.sm, gap: spacing.sm },
  sectionHeaderTitle: { flex: 1 },
  deptGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  deptCell: { width: "47%" },
  deptCard: {
    borderRadius: radius.lg,
    overflow: "hidden",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.divider,
    ...shadows.card,
  },
  deptCardSelected: { borderColor: colors.primary, borderWidth: 2 },
  deptImage: { width: "100%", height: 96, backgroundColor: colors.divider },
  deptCountBadge: {
    position: "absolute",
    top: spacing.sm,
    right: spacing.sm,
    backgroundColor: colors.overlay,
    borderRadius: radius.xs,
    paddingHorizontal: spacing.xs,
    paddingVertical: 3,
  },
  deptInfo: { padding: spacing.sm },
  productGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  productGridItem: { width: "47%" },
  trustRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.primaryLight,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.lg,
  },
});
