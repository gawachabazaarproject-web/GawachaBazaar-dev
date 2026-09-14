import React, { useMemo } from "react";
import { Image } from "expo-image";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Stack, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { QuantityStepper } from "@/components/QuantityStepper";
import { ShopHeader } from "@/components/ShopHeader";
import { RecommendationRail } from "@/components/RecommendationRail";
import { MiniProductTile } from "@/components/MiniProductTile";
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
import { colors, radius, spacing } from "@/theme";
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
        <ShopHeader
          locationLabel={defaultAddress ? `${defaultAddress.label} - ${defaultAddress.city}` : "Add an address"}
          onLocationPress={() => router.push("/address")}
          onAccountPress={() => router.push("/(tabs)/account")}
        />
        <View style={styles.closeRow}>
          <Pressable onPress={() => router.back()} hitSlop={8} style={styles.closeButton}>
            <Feather name="x" size={18} color={colors.textSecondary} />
          </Pressable>
        </View>

        {isLoading ? null : (
          <>
            <DeliverySummaryCard
              addressLabel={defaultAddress?.label ?? "Home"}
              addressLine={
                defaultAddress
                  ? `${defaultAddress.city}, ${defaultAddress.state} (${defaultAddress.postal_code})`
                  : "Add a delivery address"
              }
              onChangePress={() => router.push("/address")}
            />
            <FreeDeliveryProgress cartTotal={Number.parseFloat(cart?.total_amount ?? "0")} currency={cart?.currency ?? "INR"} />

            <View style={styles.basketHeader}>
              <View>
                <Text variant="eyebrow" color={colors.accentDark}>
                  YOUR MARKET
                </Text>
                <Text variant="h1" style={{ marginTop: spacing.xs }}>
                  Your Harvest Basket
                </Text>
                <Text variant="caption" color={colors.textSecondary} style={{ marginTop: spacing.xs }}>
                  {items.length} Farm SKUs
                </Text>
              </View>
              <Pressable onPress={() => clearCart.mutate()} disabled={clearCart.isPending}>
                <Text variant="bodySmall" color={colors.error}>
                  EMPTY CART
                </Text>
              </Pressable>
            </View>

            <View style={styles.list}>
              {items.map((item) => (
                <CartItemCard
                  key={item.id}
                  item={item}
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

            <Text variant="caption" color={colors.textSecondary} style={styles.impactNote}>
              Wholesale mandi rates: directly helping {items.length + 10} Vidarbha farmer families.
            </Text>
          </>
        )}
      </ScrollView>

      {!isLoading && items.length > 0 ? (
        <View style={[styles.stickyBar, { paddingBottom: insets.bottom, height: 68 + insets.bottom }]}>
          <View>
            <View style={styles.stickyTotalRow}>
              <Text variant="price" color={colors.textInverse}>
                {formatMoney(cart?.total_amount ?? "0", cart?.currency ?? "INR")}
              </Text>
              <View style={styles.itemCountBadge}>
                <Text variant="label" color={colors.textInverse}>
                  {items.length} ITEMS
                </Text>
              </View>
            </View>
            <Text variant="caption" color={colors.primaryLight}>
              Delivery in 25 mins
            </Text>
          </View>
          <Pressable style={styles.checkoutButton} onPress={() => router.push("/checkout")}>
            <Text variant="button" color={colors.textOnAccent}>
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
}: {
  item: CartItemResponse;
  onIncrement: () => void;
  onDecrement: () => void;
}) {
  const quantity = Math.round(Number.parseFloat(item.quantity));
  const { marathiName, origin, mrp, cartBadge } = getEmbellishment(item.product_slug);

  return (
    <View style={styles.card}>
      <View style={styles.imageWrap}>
        <Image
          source={item.primary_image_url ?? undefined}
          style={styles.image}
          contentFit="cover"
          placeholder={{ blurhash: "L4C~D%~q00~q~q00%M-;9F%M-;-;" }}
        />
        {cartBadge ? (
          <View style={styles.cartBadge}>
            <Text variant="label" color={colors.textOnAccent}>
              {cartBadge}
            </Text>
          </View>
        ) : null}
      </View>
      <View style={styles.cardInfo}>
        {origin ? (
          <Text variant="label" color={colors.accentDark} numberOfLines={1}>
            {origin.toUpperCase()}
          </Text>
        ) : null}
        <Text variant="titleSmall" numberOfLines={1}>
          {item.product_name}
          {marathiName ? <Text variant="caption" color={colors.textSecondary}> ({marathiName})</Text> : null}
        </Text>
        <Text variant="caption" color={colors.textSecondary} numberOfLines={1}>
          {item.variant_name}
        </Text>
        {item.unit_price ? (
          <View style={styles.priceRow}>
            <Text variant="priceSmall" color={colors.price}>
              {formatMoney(item.unit_price, item.currency ?? "INR")}
            </Text>
            {mrp && Number.parseFloat(mrp) > Number.parseFloat(item.unit_price) ? (
              <Text variant="caption" color={colors.strikethrough} style={styles.strike}>
                {formatMoney(mrp, item.currency ?? "INR")}
              </Text>
            ) : null}
          </View>
        ) : (
          <Text variant="bodySmall" color={colors.error}>
            Price no longer available
          </Text>
        )}
      </View>
      <QuantityStepper quantity={quantity} onAdd={onIncrement} onIncrement={onIncrement} onDecrement={onDecrement} />
    </View>
  );
}

const styles = StyleSheet.create({
  scrollContent: { paddingBottom: 130 },
  closeRow: { alignItems: "flex-end", paddingHorizontal: spacing.base },
  closeButton: { width: 32, height: 32, alignItems: "center", justifyContent: "center" },
  basketHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
    paddingHorizontal: spacing.base,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  list: { paddingHorizontal: spacing.base, marginTop: spacing.base },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderColor: colors.divider,
    paddingVertical: spacing.md,
  },
  imageWrap: { width: 88, height: 88 },
  image: { width: 88, height: 88, borderRadius: radius.none, backgroundColor: colors.background },
  cartBadge: {
    position: "absolute",
    top: 0,
    left: 0,
    backgroundColor: colors.accent,
    paddingHorizontal: 4,
    paddingVertical: 2,
  },
  cardInfo: { flex: 1 },
  priceRow: { flexDirection: "row", alignItems: "baseline", gap: spacing.xs, marginTop: 2 },
  strike: { textDecorationLine: "line-through" },
  impactNote: { marginHorizontal: spacing.base, marginTop: spacing.base, textAlign: "center" },
  stickyBar: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: 68,
    backgroundColor: colors.primary,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.base,
  },
  stickyTotalRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  itemCountBadge: { backgroundColor: colors.primaryDark, borderRadius: radius.none, paddingHorizontal: spacing.xs, paddingVertical: 2 },
  checkoutButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.accent,
    borderRadius: radius.none,
    paddingHorizontal: spacing.lg,
    height: 44,
  },
});
