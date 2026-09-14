import React from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import Animated, { FadeInUp } from "react-native-reanimated";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Skeleton } from "@/components/Skeleton";
import { ShopHeader } from "@/components/ShopHeader";
import { PressableScale } from "@/components/PressableScale";
import { CART_BAR_CLEARANCE } from "@/components/CartBar";
import { useAllProducts, useCategories } from "@/features/catalog/useCatalog";
import { useAddresses } from "@/features/address/useAddresses";
import { getCategoryPhoto } from "@/utils/categoryVisuals";
import { CATEGORY_MARATHI, getDepartments } from "@/utils/categoryDepartments";
import { colors, radius, spacing } from "@/theme";
import { CategoryResponse } from "@/types/api";

export default function CategoriesScreen() {
  const router = useRouter();
  const { data: categories, isLoading } = useCategories();
  const { data: productsData } = useAllProducts();

  const { data: addresses } = useAddresses();
  const defaultAddress = addresses?.find((a) => a.is_default) ?? addresses?.[0];
  const allProducts = productsData?.items ?? [];

  return (
    <Screen edges={["top"]}>
      <ShopHeader
        locationLabel={defaultAddress ? `${defaultAddress.label} - ${defaultAddress.city}` : "Add an address"}
        onLocationPress={() => router.push("/address")}
        onAccountPress={() => router.push("/(tabs)/account")}
        onCartPress={() => router.push("/cart")}
      />

      <Pressable style={styles.searchBar} onPress={() => router.push("/(tabs)/search")}>
        <Feather name="search" size={16} color={colors.textMuted} />
        <Text variant="body" color={colors.textMuted} style={styles.searchPlaceholder} numberOfLines={1}>
          Search groceries, staples, dairy...
        </Text>
        <Feather name="mic" size={15} color={colors.textMuted} />
      </Pressable>

      <View style={styles.heroText}>
        <Text variant="eyebrow" color={colors.accentDark}>
          BROWSE
        </Text>
        <Text variant="displayM" style={{ marginTop: spacing.xs }}>
          Shop by <Text variant="script" color={colors.primary}>category.</Text>
        </Text>
      </View>

      {isLoading ? (
        <View style={styles.loadingWrap}>
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} height={220} borderRadius={0} style={{ marginBottom: spacing.md }} />
          ))}
        </View>
      ) : (
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.list}>
          {(categories ?? []).map((category, index) => {
            const count = allProducts.filter((p) => p.category_id === category.id).length;
            const departmentCount = getDepartments(category.slug).length;
            return (
              <CategoryRow
                key={category.id}
                category={category}
                index={index}
                itemCount={count}
                departmentCount={departmentCount}
                onPress={() => router.push(`/category/${category.id}`)}
              />
            );
          })}
        </ScrollView>
      )}
    </Screen>
  );
}

function CategoryRow({
  category,
  index,
  itemCount,
  departmentCount,
  onPress,
}: {
  category: CategoryResponse;
  index: number;
  itemCount: number;
  departmentCount: number;
  onPress: () => void;
}) {
  return (
    <Animated.View entering={FadeInUp.delay(Math.min(index, 6) * 60).duration(300)}>
      <PressableScale style={styles.panel} onPress={onPress}>
        <Image source={getCategoryPhoto(category.slug)} style={styles.panelImage} contentFit="cover" transition={200} />
        <View style={styles.panelScrim} />
        <Text variant="displayL" color={colors.textInverse} style={styles.panelIndex}>
          {String(index + 1).padStart(2, "0")}
        </Text>
        <View style={styles.panelFooter}>
          <View style={{ flex: 1 }}>
            <Text variant="h1" color={colors.textInverse}>
              {category.name}
            </Text>
            <View style={styles.panelMetaRow}>
              <Text variant="caption" color="rgba(255,255,255,0.75)">
                {CATEGORY_MARATHI[category.slug] ?? ""}
              </Text>
              <Text variant="caption" color="rgba(255,255,255,0.5)">
                {itemCount} items{departmentCount > 0 ? ` · ${departmentCount} sections` : ""}
              </Text>
            </View>
          </View>
          <View style={styles.panelArrow}>
            <Feather name="arrow-up-right" size={18} color={colors.textInverse} />
          </View>
        </View>
      </PressableScale>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
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
  searchPlaceholder: { marginLeft: spacing.sm, flex: 1 },
  heroText: { paddingHorizontal: spacing.base, marginTop: spacing.xl, marginBottom: spacing.lg },
  loadingWrap: { padding: spacing.base },
  list: { paddingHorizontal: spacing.base, paddingBottom: spacing.xl + CART_BAR_CLEARANCE, gap: spacing.md },
  panel: {
    height: 220,
    borderRadius: radius.none,
    overflow: "hidden",
    backgroundColor: colors.primary,
    justifyContent: "space-between",
  },
  panelImage: { ...StyleSheet.absoluteFill },
  panelScrim: { ...StyleSheet.absoluteFill, backgroundColor: "rgba(11, 45, 32, 0.42)" },
  panelIndex: { padding: spacing.base, opacity: 0.7 },
  panelFooter: { flexDirection: "row", alignItems: "flex-end", padding: spacing.base, gap: spacing.sm },
  panelMetaRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.xs },
  panelArrow: {
    width: 34,
    height: 34,
    borderRadius: radius.none,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.5)",
    alignItems: "center",
    justifyContent: "center",
  },
});
