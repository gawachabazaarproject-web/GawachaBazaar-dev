import React, { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import Animated, { FadeInUp } from "react-native-reanimated";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Skeleton } from "@/components/Skeleton";
import { FilterChip } from "@/components/FilterChip";
import { PressableScale } from "@/components/PressableScale";
import { EmptyState } from "@/components/EmptyState";
import { ProductCard, productSummaryToCardData } from "@/components/ProductCard";
import { CART_BAR_CLEARANCE } from "@/components/CartBar";
import { useAllProducts, useCategory } from "@/features/catalog/useCatalog";
import { getCategoryPhoto } from "@/utils/categoryVisuals";
import { CATEGORY_MARATHI, getDepartments, getCategoryStory } from "@/utils/categoryDepartments";
import { colors, radius, spacing } from "@/theme";

export default function CategoryScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const categoryId = Number(id);
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { data: category, isLoading: categoryLoading } = useCategory(categoryId);
  const { data: productsData, isLoading: productsLoading } = useAllProducts();
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string | null>(null);

  const allProducts = useMemo(() => productsData?.items ?? [], [productsData]);
  const productsBySlug = useMemo(() => new Map(allProducts.map((p) => [p.slug, p])), [allProducts]);
  const categoryProducts = useMemo(
    () => (category ? allProducts.filter((p) => p.category_id === category.id) : []),
    [allProducts, category],
  );

  const departments = category ? getDepartments(category.slug) : [];
  const selectedDepartment = departments.find((d) => d.id === selectedDepartmentId) ?? null;

  const visibleProducts = useMemo(() => {
    if (!selectedDepartment) return categoryProducts;
    const slugSet = new Set(selectedDepartment.productSlugs);
    return categoryProducts.filter((p) => slugSet.has(p.slug));
  }, [categoryProducts, selectedDepartment]);

  const isLoading = categoryLoading || productsLoading || !category;

  if (isLoading) {
    return (
      <Screen edges={["bottom"]}>
        <Stack.Screen options={{ headerShown: false }} />
        <View style={{ paddingTop: insets.top + spacing.base, padding: spacing.base }}>
          <Skeleton height={240} borderRadius={0} />
        </View>
      </Screen>
    );
  }

  return (
    <Screen edges={["bottom"]}>
      <Stack.Screen options={{ headerShown: false }} />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: spacing.xl + CART_BAR_CLEARANCE }}>
        <View style={styles.hero}>
          <Image source={getCategoryPhoto(category.slug)} style={StyleSheet.absoluteFill} contentFit="cover" />
          <LinearGradient
            pointerEvents="none"
            colors={["rgba(11,45,32,0)", "rgba(11,45,32,0.08)", "rgba(11,45,32,0.4)", "rgba(11,45,32,0.68)"]}
            locations={[0, 0.35, 0.7, 1]}
            style={StyleSheet.absoluteFill}
          />
          <Pressable
            onPress={() => router.back()}
            style={[styles.backButton, { top: insets.top + spacing.sm }]}
            accessibilityRole="button"
            accessibilityLabel="Go back"
            hitSlop={8}
          >
            <Feather name="arrow-left" size={18} color={colors.textInverse} />
          </Pressable>
          <View style={styles.heroContent}>
            <Text variant="eyebrow" color={colors.accentLight}>
              VIDARBHA FARMER CLUSTERS
            </Text>
            <Text variant="displayM" color={colors.textInverse} style={{ marginTop: spacing.xs }}>
              {category.name}
            </Text>
            {CATEGORY_MARATHI[category.slug] ? (
              <Text variant="body" color="rgba(255,255,255,0.7)" style={{ marginTop: 2 }}>
                {CATEGORY_MARATHI[category.slug]}
              </Text>
            ) : null}
            <Text variant="body" color="rgba(255,255,255,0.75)" style={styles.heroStory}>
              {getCategoryStory(category.slug)}
            </Text>
          </View>
        </View>

        <View style={styles.body}>
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
                <Text variant="eyebrow" color={colors.accentDark}>
                  DEPARTMENTS
                </Text>
                <Text variant="caption" color={colors.textSecondary}>
                  {departments.length} {departments.length === 1 ? "section" : "sections"}
                </Text>
              </View>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.deptRow}>
                {departments.map((dept, index) => {
                  const thumbSlug = dept.productSlugs.find((s) => productsBySlug.has(s));
                  const thumbUrl = thumbSlug ? productsBySlug.get(thumbSlug)?.primary_image_url : null;
                  const selected = selectedDepartmentId === dept.id;
                  return (
                    <Animated.View key={dept.id} entering={FadeInUp.delay(Math.min(index, 6) * 45).duration(260)}>
                      <PressableScale
                        style={[styles.deptCard, selected && styles.deptCardSelected]}
                        onPress={() => setSelectedDepartmentId((cur) => (cur === dept.id ? null : dept.id))}
                      >
                        <Image source={thumbUrl ?? undefined} style={styles.deptImage} contentFit="cover" transition={150} />
                        <View style={styles.deptInfo}>
                          <Text variant="bodyMedium" numberOfLines={1}>
                            {dept.name}
                          </Text>
                          <Text variant="caption" color={colors.textSecondary} numberOfLines={1}>
                            {dept.productSlugs.length} items
                          </Text>
                        </View>
                      </PressableScale>
                    </Animated.View>
                  );
                })}
              </ScrollView>
            </>
          ) : null}

          <View style={styles.sectionHeader}>
            <Text variant="eyebrow" color={colors.accentDark}>
              {selectedDepartment ? selectedDepartment.name.toUpperCase() : "ALL PRODUCTS"}
            </Text>
            <Text variant="caption" color={colors.textSecondary}>
              {visibleProducts.length} {visibleProducts.length === 1 ? "item" : "items"}
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
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { height: 260, backgroundColor: colors.primary },
  backButton: {
    position: "absolute",
    left: spacing.base,
    width: 36,
    height: 36,
    borderRadius: radius.none,
    backgroundColor: "rgba(11, 45, 32, 0.55)",
    alignItems: "center",
    justifyContent: "center",
  },
  heroContent: { position: "absolute", left: spacing.base, right: spacing.base, bottom: spacing.lg },
  heroStory: { marginTop: spacing.sm, maxWidth: "92%" },
  body: { padding: spacing.base },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  sectionHeader: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", marginTop: spacing.xl, marginBottom: spacing.md },
  deptRow: { gap: spacing.md },
  deptCard: {
    width: 140,
    borderRadius: radius.none,
    overflow: "hidden",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.divider,
  },
  deptCardSelected: { borderColor: colors.primary, borderWidth: 2 },
  deptImage: { width: "100%", height: 96, backgroundColor: colors.divider },
  deptInfo: { padding: spacing.sm },
  productGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  productGridItem: { width: "47%" },
});
