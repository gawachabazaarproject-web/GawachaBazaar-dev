import React, { useMemo } from "react";
import { Image } from "expo-image";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Stack, useRouter } from "expo-router";
import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { EmptyState } from "@/components/EmptyState";
import { RecommendationRail } from "@/components/RecommendationRail";
import { MiniProductTile } from "@/components/MiniProductTile";
import { CartHeaderArt } from "@/components/cart/CartHeaderArt";
import { DeliverySummaryCard } from "@/components/cart/DeliverySummaryCard";
import { FreeDeliveryProgress } from "@/components/cart/FreeDeliveryProgress";
import { DeliveryInstructionCard } from "@/components/cart/DeliveryInstructionCard";
import { BillBreakdownCard } from "@/components/cart/BillBreakdownCard";
import { formatMoney } from "@/utils/money";
import { getEmbellishment } from "@/utils/productEmbellishments";
import {
  useCart,
  useClearCart,
  useRemoveCartItem,
  useUpdateCartItemQuantity,
} from "@/features/cart/useCart";
import { useAddresses } from "@/features/address/useAddresses";
import { useProducts } from "@/features/catalog/useCatalog";
import { productSummaryToCardData } from "@/components/ProductCard";
import { colors, spacing } from "@/theme";
import { CartItemResponse } from "@/types/api";

const ADDON_SLUGS = ["fresh-lemons", "curry-leaves", "fresh-coriander", "green-chillies"];

export default function CartScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { data: cart, isLoading } = useCart();
  const updateItem = useUpdateCartItemQuantity();
  const removeItem = useRemoveCartItem();
  const clearCart = useClearCart();
  const { data: addresses } = useAddresses();
  const { data: allData } = useProducts({});

  const items = cart?.items ?? [];
  const defaultAddress = addresses?.find((a) => a.is_default) ?? addresses?.[0];
  const allProducts = allData?.pages.flatMap((p) => p.items) ?? [];

  const addonProducts = useMemo(() => {
    const inCart = new Set(items.map((i) => i.product_slug));
    return ADDON_SLUGS.map((slug) => allProducts.find((p) => p.slug === slug))
      .filter((p): p is NonNullable<typeof p> => !!p && !inCart.has(p.slug))
      .map(productSummaryToCardData);
  }, [allProducts, items]);

  if (!isLoading && items.length === 0) {
    return (
      <Screen>
        <Stack.Screen options={{ headerShown: true, title: "Your cart" }} />
        <EmptyState
          icon="shopping-cart"
          title="Your cart is empty"
          message="Find something you'll love."
          actionLabel="Start shopping"
          onAction={() => router.replace("/(tabs)")}
        />
      </Screen>
    );
  }

  return (
    <Screen edges={["top"]}>
      <Stack.Screen options={{ headerShown: false }} />
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <CartHeaderArt />
        <View style={styles.topRow}>
          <Pressable
            onPress={() => router.back()}
            hitSlop={8}
            style={styles.backButton}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Feather name="chevron-left" size={24} color={colors.textPrimary} />
          </Pressable>
          <View style={{ flex: 1 }}>
            <DeliverySummaryCard
              addressLabel={defaultAddress?.label ?? "Home"}
              addressLine={
                defaultAddress ? `${defaultAddress.label} - ${defaultAddress.city}` : "Add a delivery address"
              }
              onChangePress={() => router.push("/address")}
            />
          </View>
          <Pressable
            onPress={() => router.push("/(tabs)/account")}
            style={styles.accountButton}
            accessibilityRole="button"
            accessibilityLabel="Account"
          >
            <Feather name="user" size={20} color={colors.textPrimary} />
          </Pressable>
        </View>

        {isLoading ? null : (
          <>
            <FreeDeliveryProgress
              cartTotal={Number.parseFloat(cart?.total_amount ?? "0")}
              currency={cart?.currency ?? "INR"}
            />

            <View style={styles.basketHeader}>
              <View style={styles.marketRow}>
                <Text variant="eyebrow" color={colors.accentDark}>
                  YOUR MARKET
                </Text>
                <Feather name="feather" size={16} color={colors.success} />
              </View>
              <Text variant="displayM" color={colors.primary} style={styles.basketTitle}>
                Your Harvest Basket
              </Text>
              <View style={styles.basketMeta}>
                <Text variant="bodySmall" color={colors.textSecondary}>
                  {items.length} {items.length === 1 ? "item" : "items"} · From local farms
                </Text>
                <Pressable
                  onPress={() => clearCart.mutate()}
                  disabled={clearCart.isPending}
                  style={styles.clearButton}
                  accessibilityRole="button"
                  accessibilityLabel="Clear cart"
                >
                  <Feather name="trash-2" size={13} color={colors.error} />
                  <Text variant="caption" color={colors.error} style={styles.clearText}>
                    Clear
                  </Text>
                </Pressable>
              </View>
            </View>

            <View style={styles.list}>
              {items.map((item) => (
                <CartItemCard
                  key={item.id}
                  item={item}
                  onRemove={() => removeItem.mutate(item.id)}
                  onIncrement={() =>
                    updateItem.mutate({ itemId: item.id, quantity: Math.round(Number.parseFloat(item.quantity)) + 1 })
                  }
                  onDecrement={() => {
                    const qty = Math.round(Number.parseFloat(item.quantity));
                    if (qty <= 1) removeItem.mutate(item.id);
                    else updateItem.mutate({ itemId: item.id, quantity: qty - 1 });
                  }}
                />
              ))}
            </View>

            {addonProducts.length > 0 ? (
              <RecommendationRail title="Village Mandi Add-ons" subtitle="Frequently added by Manish Nagar households">
                {addonProducts.map((p) => (
                  <MiniProductTile key={p.id} product={p} onPress={() => router.push(`/product/${p.id}`)} />
                ))}
              </RecommendationRail>
            ) : null}

            <DeliveryInstructionCard />
            <BillBreakdownCard items={items} totalAmount={cart?.total_amount ?? null} currency={cart?.currency ?? null} />

            <View style={styles.impactCard}>
              <MaterialCommunityIcons name="sprout-outline" size={22} color={colors.textPrimary} />
              <Text variant="caption" color={colors.textSecondary} style={{ flex: 1 }}>
                Wholesale mandi rates directly helping {items.length + 10} Vidarbha farmer families.
              </Text>
            </View>
          </>
        )}
      </ScrollView>

      {!isLoading && items.length > 0 ? (
        <View style={[styles.stickyBar, { marginBottom: insets.bottom + spacing.md }]}>
          <View style={{ flexShrink: 1 }}>
            <View style={styles.stickyTotalRow}>
              <Text variant="priceLarge" color={colors.textInverse}>
                {formatMoney(cart?.total_amount ?? "0", cart?.currency ?? "INR")}
              </Text>
              <View style={styles.stickyDivider} />
              <Text variant="bodySmall" color={colors.textInverse}>
                {items.length} {items.length === 1 ? "item" : "items"}
              </Text>
            </View>
            <View style={styles.etaRow}>
              <Feather name="clock" size={14} color={colors.primaryLight} />
              <Text variant="caption" color={colors.primaryLight}>
                Delivery in 25 mins
              </Text>
            </View>
          </View>
          <Pressable style={styles.checkoutButton} onPress={() => router.push("/checkout")}>
            <Text variant="bodyMedium" color={colors.textOnAccent}>
              Proceed to Pay
            </Text>
            <Feather name="arrow-right" size={16} color={colors.textOnAccent} />
          </Pressable>
        </View>
      ) : null}
    </Screen>
  );
}

function CartItemCard({
  item,
  onIncrement,
  onDecrement,
  onRemove,
}: {
  item: CartItemResponse;
  onIncrement: () => void;
  onDecrement: () => void;
  onRemove: () => void;
}) {
  const quantity = Math.round(Number.parseFloat(item.quantity));
  const { origin, cartBadge } = getEmbellishment(item.product_slug);
  const tag = cartBadge ?? origin ?? null;

  return (
    <View style={styles.card}>
      <Image
        source={item.primary_image_url ?? undefined}
        style={styles.image}
        contentFit="cover"
        placeholder={{ blurhash: "L4C~D%~q00~q~q00%M-;9F%M-;-;" }}
      />
      <View style={styles.cardInfo}>
        <View style={styles.cardTop}>
          {tag ? (
            <View style={styles.tagPill}>
              <Feather name="feather" size={11} color={colors.primary} />
              <Text variant="label" color={colors.primaryDark} numberOfLines={1}>
                {tag.toUpperCase()}
              </Text>
            </View>
          ) : (
            <View />
          )}
          <Pressable onPress={onRemove} hitSlop={8} accessibilityRole="button" accessibilityLabel="Remove item">
            <Feather name="trash-2" size={16} color={colors.textSecondary} />
          </Pressable>
        </View>
        <Text variant="titleSmall" numberOfLines={1}>
          {item.product_name}
        </Text>
        <Text variant="caption" color={colors.textSecondary} numberOfLines={1}>
          {item.variant_name}
        </Text>
        <View style={styles.cardBottom}>
          {item.unit_price ? (
            <Text variant="price" color={colors.price}>
              {formatMoney(item.unit_price, item.currency ?? "INR")}
            </Text>
          ) : (
            <Text variant="bodySmall" color={colors.error}>
              Price no longer available
            </Text>
          )}
          <View style={styles.stepper}>
            <Pressable
              onPress={onDecrement}
              hitSlop={8}
              style={styles.stepBtn}
              accessibilityRole="button"
              accessibilityLabel="Decrease quantity"
            >
              <Feather name="minus" size={14} color={colors.textPrimary} />
            </Pressable>
            <Text variant="price" style={styles.qty}>
              {quantity}
            </Text>
            <Pressable
              onPress={onIncrement}
              hitSlop={8}
              style={styles.stepBtn}
              accessibilityRole="button"
              accessibilityLabel="Increase quantity"
            >
              <Feather name="plus" size={14} color={colors.textPrimary} />
            </Pressable>
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  scrollContent: { paddingBottom: 110 },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.base,
    paddingTop: spacing.md,
  },
  backButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.divider,
    alignItems: "center",
    justifyContent: "center",
  },
  accountButton: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOpacity: 0.08,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  basketHeader: { paddingHorizontal: spacing.base, marginTop: spacing.xl },
  basketMeta: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 2 },
  clearButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    height: 28,
    backgroundColor: "#FBECEC",
    borderRadius: 14,
    paddingHorizontal: 12,
  },
  clearText: { fontSize: 12.5, lineHeight: 16, fontWeight: "500" },
  basketTitle: { marginTop: 2, fontSize: 30, lineHeight: 36 },
  marketRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  list: { paddingHorizontal: spacing.base, marginTop: spacing.md, gap: spacing.sm },
  card: {
    flexDirection: "row",
    gap: spacing.sm,
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: spacing.sm,
  },
  image: { width: 76, height: 76, borderRadius: 12, backgroundColor: colors.background },
  cardInfo: { flex: 1, justifyContent: "space-between" },
  cardTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  tagPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    backgroundColor: colors.primaryLight,
    borderRadius: 999,
    paddingHorizontal: 7,
    paddingVertical: 3,
    maxWidth: "80%",
  },
  cardBottom: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: spacing.xs },
  stepper: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.divider,
    borderRadius: 999,
    height: 30,
  },
  stepBtn: { width: 28, height: 30, alignItems: "center", justifyContent: "center" },
  qty: { minWidth: 20, textAlign: "center", fontSize: 15 },
  impactCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginHorizontal: spacing.base,
    marginTop: spacing.lg,
    padding: spacing.md,
    borderRadius: 14,
    backgroundColor: colors.divider,
  },
  stickyBar: {
    position: "absolute",
    left: spacing.sm,
    right: spacing.sm,
    bottom: 0,
    backgroundColor: colors.primary,
    borderRadius: 26,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    paddingLeft: spacing.base,
    paddingRight: spacing.sm,
    gap: spacing.sm,
  },
  stickyTotalRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  stickyDivider: { width: 1, height: 22, backgroundColor: "rgba(255,255,255,0.4)" },
  etaRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 4 },
  checkoutButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.accent,
    borderRadius: 999,
    paddingHorizontal: spacing.base,
    height: 42,
  },
});
