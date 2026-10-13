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
import { PressableScale } from "@/components/PressableScale";
import { EmptyState } from "@/components/EmptyState";
import { ProductCard, productSummaryToCardData } from "@/components/ProductCard";
import { CART_BAR_CLEARANCE } from "@/components/CartBar";
import { useAllProducts, useCategory } from "@/features/catalog/useCatalog";
import { getCategoryPhoto } from "@/utils/categoryVisuals";
import { CATEGORY_MARATHI, getDepartments, getCategoryStory } from "@/utils/categoryDepartments";
import { ProductSummaryResponse } from "@/types/api";
import { colors, radius, spacing } from "@/theme";

interface Section {
  id: string;
  name: string;
  imageUrl: string | null;
  matches: (p: ProductSummaryResponse) => boolean;
}

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
  // Subcategories an admin created are the sections; the hand-curated
  // departments remain only as a fallback for categories without any.
  const sections = useMemo<Section[]>(() => {
    if (!category) return [];
    if (category.children.length > 0) {
      return category.children.map((child) => ({
        id: String(child.id),
        name: child.name,
        imageUrl: getCategoryPhoto(child.slug, child.image_url),
        matches: (p: ProductSummaryResponse) => p.category_id === child.id,
      }));
    }
    return getDepartments(category.slug).map((dept) => {
      const slugSet = new Set(dept.productSlugs);
      const thumbSlug = dept.productSlugs.find((s) => productsBySlug.has(s));
      return {
        id: dept.id,
        name: dept.name,
        imageUrl: (thumbSlug ? productsBySlug.get(thumbSlug)?.primary_image_url : null) ?? null,
        matches: (p: ProductSummaryResponse) => slugSet.has(p.slug),
      };
    });
  }, [category, productsBySlug]);

  const categoryProducts = useMemo(() => {
    if (!category) return [];
    const ids = new Set([category.id, ...category.children.map((c) => c.id)]);
    return allProducts.filter((p) => ids.has(p.category_id));
  }, [allProducts, category]);

  const selectedSection = sections.find((s) => s.id === selectedDepartmentId) ?? null;
  const toggleSection = (id: string) => setSelectedDepartmentId((cur) => (cur === id ? null : id));

  const visibleProducts = useMemo(
    () => (selectedSection ? categoryProducts.filter(selectedSection.matches) : categoryProducts),
    [categoryProducts, selectedSection],
  );

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
          <Image source={getCategoryPhoto(category.slug, category.image_url)} style={StyleSheet.absoluteFill} contentFit="cover" />
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
          {sections.length > 0 ? (
            <>
              <View style={[styles.sectionHeader, { marginTop: spacing.xs }]}>
                <Text variant="eyebrow" color={colors.accentDark}>
                  {category.children.length > 0 ? "SUBCATEGORIES" : "DEPARTMENTS"}
                </Text>
                <Text variant="caption" color={colors.textSecondary}>
                  {sections.length} {sections.length === 1 ? "section" : "sections"}
                </Text>
              </View>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.deptRow}>
                <PressableScale
                  style={[styles.tile, !selectedSection && styles.tileSelected]}
                  onPress={() => setSelectedDepartmentId(null)}
                >
                  <Image source={getCategoryPhoto(category.slug, category.image_url)} style={StyleSheet.absoluteFill} contentFit="cover" transition={150} />
                  <LinearGradient pointerEvents="none" colors={["rgba(11,45,32,0.05)", "rgba(11,45,32,0.72)"]} style={StyleSheet.absoluteFill} />
                  <View style={styles.tileLabel}>
                    <Text variant="bodyMedium" color={colors.textInverse} numberOfLines={2}>
                      All
                    </Text>
                    <Text variant="caption" color="rgba(255,255,255,0.75)">
                      {categoryProducts.length} items
                    </Text>
                  </View>
                </PressableScale>
                {sections.map((section, index) => {
                  const selected = selectedDepartmentId === section.id;
                  const count = categoryProducts.filter(section.matches).length;
                  return (
                    <Animated.View key={section.id} entering={FadeInUp.delay(Math.min(index, 6) * 45).duration(260)}>
                      <PressableScale style={[styles.tile, selected && styles.tileSelected]} onPress={() => toggleSection(section.id)}>
                        <Image source={section.imageUrl ?? undefined} style={StyleSheet.absoluteFill} contentFit="cover" transition={150} />
                        <LinearGradient pointerEvents="none" colors={["rgba(11,45,32,0.05)", "rgba(11,45,32,0.72)"]} style={StyleSheet.absoluteFill} />
                        {selected ? (
                          <View style={styles.tileCheck}>
                            <Feather name="check" size={12} color={colors.primary} />
                          </View>
                        ) : null}
                        <View style={styles.tileLabel}>
                          <Text variant="bodyMedium" color={colors.textInverse} numberOfLines={2}>
                            {section.name}
                          </Text>
                          <Text variant="caption" color="rgba(255,255,255,0.75)">
                            {count} {count === 1 ? "item" : "items"}
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
              {selectedSection ? selectedSection.name.toUpperCase() : "ALL PRODUCTS"}
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
    borderRadius: radius.card,
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
  tile: {
    width: 128,
    height: 148,
    borderRadius: radius.card,
    overflow: "hidden",
    backgroundColor: colors.primary,
    borderWidth: 2,
    borderColor: "transparent",
    justifyContent: "flex-end",
  },
  tileSelected: { borderColor: colors.accent },
  tileLabel: { padding: spacing.sm },
  tileCheck: {
    position: "absolute",
    top: spacing.sm,
    right: spacing.sm,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  // No column gap: 2 x 49.5% + a fixed gap overflows the row on phones
  // under ~400dp and every card wrapped into a single column. The 1% left
  // over by space-between is the seam instead.
  productGrid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", rowGap: spacing.xs },
  // 49.5% (was 47%) - matches ProductGrid's own tightened two-column
  // math so cards read the same width whether reached via Search or here.
  productGridItem: { width: "49.5%" },
});
