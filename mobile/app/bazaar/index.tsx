import React, { useMemo, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Stack, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { FilterChip } from "@/components/FilterChip";
import { ProductCard, productSummaryToCardData } from "@/components/ProductCard";
import { ProductCardSkeleton } from "@/components/Skeleton";
import { useCategories, useProducts } from "@/features/catalog/useCatalog";
import { useBazaarStatus, useCartProductCount } from "@/features/bazaar/useBazaar";
import { useAuthStore } from "@/store/authStore";
import { colors, fontFamily, radius, spacing } from "@/theme";

/** Mirrors the backend defaults (FREE_DELIVERY_MIN_ITEMS / BAZAAR_PLUS_*);
 * live values from /bazaar/status win when available. */
const DEFAULT_MIN_ITEMS = 15;
const DEFAULT_ORDERS_REQUIRED = 6;

/** Planned Gawacha Bazaar+ perks. These are announcements of what is coming,
 * not features that exist today - edit the list as the plan changes. */
const UPCOMING_BENEFITS: { icon: keyof typeof Feather.glyphMap; title: string; body: string }[] = [
  { icon: "truck", title: "Free delivery on every order", body: "Not just Bazaars - any basket, any size." },
  { icon: "clock", title: "Priority delivery slots", body: "Pick the best harvest slots before everyone else." },
  { icon: "tag", title: "Members-only prices", body: "Special rates on seasonal farm produce." },
  { icon: "sunrise", title: "Early access to new arrivals", body: "First look at fresh-from-farm picks." },
  { icon: "gift", title: "Monthly freshness surprise", body: "A little something from our village partners." },
];

export default function BazaarScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const signedIn = useAuthStore((s) => s.status === "authenticated");
  const cartItems = useCartProductCount();
  const { data: status } = useBazaarStatus();
  const { data: categories } = useCategories();
  const [categoryId, setCategoryId] = useState<number | null>(null);

  const { data, isLoading, isFetchingNextPage, fetchNextPage, hasNextPage } = useProducts(
    categoryId ? { categoryId } : { q: undefined },
  );
  const products = useMemo(
    () => (data?.pages.flatMap((p) => p.items) ?? []).map(productSummaryToCardData),
    [data],
  );

  const minItems = status?.free_delivery_min_items ?? DEFAULT_MIN_ITEMS;
  const ordersRequired = status?.orders_required ?? DEFAULT_ORDERS_REQUIRED;
  const bazaarOrders = Math.min(status?.bazaar_orders_in_window ?? 0, ordersRequired);
  const eligible = status?.eligible_for_bazaar_plus ?? false;
  const unlocked = cartItems >= minItems;
  const remaining = Math.max(0, minItems - cartItems);

  // Shown after the product list (below the products, not above them).
  const plusSection = (
    <View>
      {/* Gawacha Bazaar+ */}
      <View style={[styles.pad, styles.plusWrap]}>
        <View style={styles.plusCard}>
          <View style={styles.plusTop}>
            <View style={styles.plusBadge}>
              <Feather name="award" size={13} color={colors.primaryDark} />
              <Text variant="eyebrow" color={colors.primaryDark}>
                BAZAAR+
              </Text>
            </View>
            <Text variant="caption" color={colors.textSecondary}>
              {bazaarOrders}/{ordersRequired} this month
            </Text>
          </View>
          <Text variant="displayM" color={colors.primary} style={styles.plusTitle}>
            {eligible ? "You are in Gawacha Bazaar+" : "Gawacha Bazaar+ membership"}
          </Text>
          <Text variant="bodySmall" color={colors.textSecondary} style={styles.plusBody}>
            {eligible
              ? `${ordersRequired} Bazaars this month - thank you for shopping the village way.`
              : `Place ${ordersRequired} Bazaars (${minItems}+ different products each) in a calendar month to become eligible. Cancelled orders do not count.`}
          </Text>
          <View style={styles.stampRow}>
            {Array.from({ length: ordersRequired }).map((_, i) => {
              const filled = i < bazaarOrders;
              return (
                <View key={i} style={[styles.stamp, filled && styles.stampFilled]}>
                  {filled ? (
                    <Feather name="check" size={14} color={colors.primaryDark} />
                  ) : (
                    <Text variant="caption" color={colors.textMuted}>
                      {i + 1}
                    </Text>
                  )}
                </View>
              );
            })}
          </View>
          {!signedIn ? (
            <Text variant="caption" color={colors.textMuted} style={styles.hint}>
              Sign in to track your Bazaars.
            </Text>
          ) : null}

          <View style={styles.benefitsHead}>
            <Text variant="eyebrow" color={colors.accentDark}>
              UPCOMING BENEFITS
            </Text>
            <View style={styles.soon}>
              <Text variant="label" color={colors.accentDark}>
                COMING SOON
              </Text>
            </View>
          </View>
          {UPCOMING_BENEFITS.map((b, i) => (
            <View key={b.title} style={[styles.benefit, i < UPCOMING_BENEFITS.length - 1 && styles.benefitDivider]}>
              <View style={styles.benefitIcon}>
                <Feather name={b.icon} size={18} color={colors.primary} />
              </View>
              <View style={styles.benefitText}>
                <Text variant="bodyMedium" color={colors.textPrimary} style={styles.benefitTitle}>
                  {b.title}
                </Text>
                <Text variant="caption" color={colors.textSecondary}>
                  {b.body}
                </Text>
              </View>
            </View>
          ))}
        </View>
      </View>
    </View>
  );

  const header = (
    <View>
      {/* Offer + 15-item indicator */}
      <View style={styles.pad}>
        <LinearGradient
          colors={["#0F3B2B", "#0A2A1F", "#061A12"]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.hero}
        >
          <View style={styles.glow} pointerEvents="none" />
          <Text variant="eyebrow" color={colors.accentLight}>
            THE BAZAAR OFFER
          </Text>
          <Text variant="displayL" color={colors.textInverse} style={styles.heroTitle}>
            Fill your{" "}
            <Text variant="scriptLarge" color={colors.accentLight}>
              Bazaar.
            </Text>
          </Text>
          <Text variant="body" color="rgba(255,255,255,0.78)" style={styles.heroSub}>
            Pick {minItems} different products in one basket and we deliver it free.
          </Text>

          <View style={styles.counterRow}>
            <Text variant="displayXL" color={colors.accent} style={styles.counter}>
              {Math.min(cartItems, minItems)}
            </Text>
            <Text variant="displayM" color="rgba(255,255,255,0.55)" style={styles.counterOf}>
              / {minItems}
            </Text>
            <View style={styles.counterLabel}>
              <Text variant="eyebrow" color="rgba(255,255,255,0.6)">
                PRODUCTS IN YOUR BASKET
              </Text>
            </View>
          </View>

          {/* One dot per product slot */}
          <View style={styles.dotGrid}>
            {Array.from({ length: minItems }).map((_, i) => {
              const filled = i < cartItems;
              return (
                <View key={i} style={[styles.slot, filled && styles.slotFilled, filled && unlocked && styles.slotDone]}>
                  {filled ? (
                    <Feather name="check" size={13} color={colors.primaryDark} />
                  ) : (
                    <Text variant="caption" color="rgba(255,255,255,0.4)">
                      {i + 1}
                    </Text>
                  )}
                </View>
              );
            })}
          </View>

          <View style={styles.statusPill}>
            <Feather name={unlocked ? "check-circle" : "truck"} size={16} color={colors.primaryDark} />
            <Text variant="bodySmall" color={colors.primaryDark} style={styles.statusText}>
              {unlocked
                ? "Bazaar unlocked - delivery is free"
                : cartItems === 0
                  ? `Add ${minItems} different products for free delivery`
                  : `${remaining} more different ${remaining === 1 ? "product" : "products"} for free delivery`}
            </Text>
          </View>
        </LinearGradient>
      </View>

      {/* Product list heading + category filter */}
      <View style={styles.listHead}>
        <Text variant="eyebrow" color={colors.accentDark}>
          BUILD YOUR BASKET
        </Text>
        <Text variant="displayM" color={colors.primary} style={styles.listTitle}>
          All products
        </Text>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
        <FilterChip label="All" selected={categoryId === null} onPress={() => setCategoryId(null)} />
        {categories?.map((c) => (
          <FilterChip key={c.id} label={c.name} selected={categoryId === c.id} onPress={() => setCategoryId(c.id)} />
        ))}
      </ScrollView>
    </View>
  );

  return (
    <Screen edges={["top"]}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={styles.topBar}>
        <Pressable onPress={() => router.back()} hitSlop={10} accessibilityRole="button" accessibilityLabel="Go back">
          <Feather name="arrow-left" size={24} color={colors.textPrimary} />
        </Pressable>
        <Text variant="displayM" color={colors.primary} style={styles.topTitle}>
          Your Bazaar
        </Text>
      </View>

      {isLoading ? (
        <ScrollView showsVerticalScrollIndicator={false}>
          {header}
          <View style={styles.skeletonGrid}>
            {[1, 2, 3, 4].map((i) => (
              <View key={i} style={styles.skeletonCol}>
                <ProductCardSkeleton />
              </View>
            ))}
          </View>
          {plusSection}
        </ScrollView>
      ) : (
        <FlatList
          data={products}
          keyExtractor={(item) => String(item.id)}
          numColumns={2}
          columnWrapperStyle={styles.row}
          contentContainerStyle={{ paddingBottom: 110 + insets.bottom }}
          ListHeaderComponent={header}
          ListEmptyComponent={
            <Text variant="bodySmall" color={colors.textMuted} align="center" style={styles.empty}>
              No products in this category yet.
            </Text>
          }
          renderItem={({ item, index }) => (
            <View style={styles.col}>
              <ProductCard product={item} onPress={() => router.push(`/product/${item.id}`)} index={index % 8} />
            </View>
          )}
          ListFooterComponent={
            <View>
              {isFetchingNextPage ? (
                <View style={styles.footer}>
                  <ActivityIndicator color={colors.primary} />
                </View>
              ) : null}
              {plusSection}
            </View>
          }
          onEndReachedThreshold={0.4}
          onEndReached={() => hasNextPage && fetchNextPage()}
          showsVerticalScrollIndicator={false}
        />
      )}

      {/* Basket bar */}
      <View style={[styles.bar, { paddingBottom: insets.bottom + spacing.sm }]}>
        <View style={styles.barText}>
          <Text variant="eyebrow" color={colors.accentDark}>
            {unlocked ? "FREE DELIVERY UNLOCKED" : "YOUR BAZAAR"}
          </Text>
          <Text variant="bodyMedium" color={colors.primary}>
            {Math.min(cartItems, minItems)}/{minItems} products
            {!unlocked && cartItems > 0 ? ` · ${remaining} to go` : ""}
          </Text>
          <View style={styles.barTrack}>
            <View
              style={[styles.barFill, { width: `${Math.min(1, cartItems / minItems) * 100}%` }, unlocked && styles.barFillDone]}
            />
          </View>
        </View>
        <Pressable
          onPress={() => router.push("/cart")}
          style={({ pressed }) => [styles.barBtn, pressed && { opacity: 0.85 }]}
          accessibilityRole="button"
          accessibilityLabel="View basket"
        >
          <Text variant="bodyMedium" color={colors.textInverse}>
            View basket
          </Text>
          <Feather name="arrow-right" size={16} color={colors.textInverse} />
        </Pressable>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  pad: { paddingHorizontal: spacing.base },
  topBar: { flexDirection: "row", alignItems: "center", gap: spacing.base, paddingHorizontal: spacing.base, paddingVertical: spacing.md },
  topTitle: { fontSize: 21, lineHeight: 27 },

  hero: { borderRadius: 24, padding: spacing.lg, overflow: "hidden" },
  glow: {
    position: "absolute",
    top: -70,
    right: -60,
    width: 220,
    height: 220,
    borderRadius: 110,
    backgroundColor: "rgba(217,165,42,0.16)",
  },
  heroTitle: { marginTop: spacing.sm, fontSize: 30, lineHeight: 40 },
  heroSub: { marginTop: spacing.sm, fontSize: 13.5, lineHeight: 20 },
  counterRow: { flexDirection: "row", alignItems: "flex-end", marginTop: spacing.lg, gap: spacing.sm },
  counter: { fontSize: 56, lineHeight: 64 },
  counterOf: { marginBottom: 10 },
  counterLabel: { flex: 1, marginBottom: 14, marginLeft: spacing.xs },
  dotGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: spacing.sm },
  slot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1.5,
    borderStyle: "dashed",
    borderColor: "rgba(255,255,255,0.3)",
    alignItems: "center",
    justifyContent: "center",
  },
  slotFilled: { backgroundColor: colors.accent, borderStyle: "solid", borderColor: colors.accent },
  slotDone: { backgroundColor: "#7FD6A0", borderColor: "#7FD6A0" },
  statusPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.accentLight,
    borderRadius: radius.pill,
    paddingVertical: spacing.sm + 2,
    paddingHorizontal: spacing.base,
    marginTop: spacing.lg,
  },
  statusText: { flex: 1, fontFamily: fontFamily.semibold },

  plusWrap: { marginTop: spacing.lg },
  plusCard: {
    backgroundColor: colors.surface,
    borderRadius: 22,
    padding: spacing.lg,
    shadowColor: "#143326",
    shadowOpacity: 0.07,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  },
  plusTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  plusBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: colors.accentLight,
    borderRadius: radius.pill,
    paddingVertical: 4,
    paddingHorizontal: spacing.md,
  },
  plusTitle: { marginTop: spacing.md, fontSize: 22, lineHeight: 28 },
  plusBody: { marginTop: spacing.xs, lineHeight: 19 },
  stampRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.base },
  stamp: {
    width: 34,
    height: 34,
    borderRadius: 17,
    borderWidth: 1.5,
    borderStyle: "dashed",
    borderColor: colors.borderStrong,
    alignItems: "center",
    justifyContent: "center",
  },
  stampFilled: { backgroundColor: colors.accent, borderStyle: "solid", borderColor: colors.accent },
  hint: { marginTop: spacing.sm },
  benefitsHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.xl,
    paddingTop: spacing.base,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  soon: { backgroundColor: colors.warningLight, borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 4 },
  benefit: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingVertical: spacing.md },
  benefitDivider: { borderBottomWidth: 1, borderBottomColor: colors.divider },
  benefitIcon: {
    width: 38,
    height: 38,
    borderRadius: 11,
    backgroundColor: colors.successLight,
    alignItems: "center",
    justifyContent: "center",
  },
  benefitText: { flex: 1 },
  benefitTitle: { fontSize: 14 },

  listHead: { paddingHorizontal: spacing.base, marginTop: spacing.xl },
  listTitle: { fontSize: 24, lineHeight: 30, marginTop: 2 },
  chips: { gap: spacing.sm, paddingHorizontal: spacing.base, paddingVertical: spacing.md },

  row: { gap: spacing.xs, paddingHorizontal: spacing.xs },
  col: { flex: 1, marginBottom: spacing.xs },
  skeletonGrid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", padding: spacing.xs, rowGap: spacing.xs },
  skeletonCol: { width: "49.5%" },
  empty: { marginTop: spacing.xl },
  footer: { paddingVertical: spacing.lg },

  bar: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
    backgroundColor: colors.surface,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    paddingTop: spacing.md,
    paddingHorizontal: spacing.base,
    shadowColor: "#000",
    shadowOpacity: 0.08,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: -3 },
    elevation: 10,
  },
  barText: { flex: 1 },
  barTrack: { height: 5, borderRadius: 3, backgroundColor: colors.divider, marginTop: 6, overflow: "hidden" },
  barFill: { height: "100%", borderRadius: 3, backgroundColor: colors.accent },
  barFillDone: { backgroundColor: colors.brandGreen },
  barBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.primary,
    borderRadius: radius.pill,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
  },
});
