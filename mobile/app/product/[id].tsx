import React, { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, Share, StyleSheet, useWindowDimensions, View } from "react-native";
import { Image } from "expo-image";
import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather, Ionicons } from "@expo/vector-icons";
import Animated, { FadeInUp } from "react-native-reanimated";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { WishlistButton } from "@/components/WishlistButton";
import { PriceTag } from "@/components/PriceTag";
import { Skeleton } from "@/components/Skeleton";
import { ProductCard, productSummaryToCardData } from "@/components/ProductCard";
import { useProduct, useProducts } from "@/features/catalog/useCatalog";
import { useVariantStepper } from "@/features/cart/useCart";
import { formatMoney, formatRatePerUnit, formatVariantSize } from "@/utils/money";
import { getEmbellishment } from "@/utils/productEmbellishments";
import { colors, radius, spacing } from "@/theme";
import { ProductVariantResponse } from "@/types/api";

/** All-caps catalogue names ("APPLE") read as shouting on this screen. */
function displayName(name: string): string {
  if (name !== name.toUpperCase()) return name;
  return name.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase());
}

/** Outlined pill stepper from the design: plain minus, count, dark plus dot.
 * Shows 1 before the item is in the cart; the plus then adds it. */
function PillStepper({
  quantity,
  disabled,
  onAdd,
  onIncrement,
  onDecrement,
  small = false,
}: {
  quantity: number;
  disabled: boolean;
  onAdd: () => void;
  onIncrement: () => void;
  onDecrement: () => void;
  small?: boolean;
}) {
  const dot = small ? 34 : 44;
  return (
    <View style={[styles.pillStepper, small && styles.pillStepperSmall, disabled && styles.disabled]}>
      <Pressable
        onPress={onDecrement}
        disabled={disabled || quantity <= 0}
        hitSlop={8}
        style={styles.pillMinus}
        accessibilityRole="button"
        accessibilityLabel="Decrease quantity"
      >
        <Feather name="minus" size={small ? 16 : 20} color={colors.primary} />
      </Pressable>
      <Text variant="price" color={colors.textPrimary} style={styles.pillCount}>
        {Math.max(quantity, 1)}
      </Text>
      <Pressable
        onPress={quantity > 0 ? onIncrement : onAdd}
        disabled={disabled}
        hitSlop={8}
        style={[styles.pillPlus, { width: dot, height: dot, borderRadius: dot / 2 }]}
        accessibilityRole="button"
        accessibilityLabel="Increase quantity"
      >
        <Feather name="plus" size={small ? 16 : 20} color={colors.textInverse} />
      </Pressable>
    </View>
  );
}

export default function ProductDetailScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { width: SCREEN_WIDTH } = useWindowDimensions();
  const IMAGE_HEIGHT = SCREEN_WIDTH * 1.05;
  const { id } = useLocalSearchParams<{ id: string }>();
  const productId = Number(id);
  const { data: product, isLoading } = useProduct(productId);
  const [activeImage, setActiveImage] = useState(0);

  const [selectedVariant, setSelectedVariant] = useState<ProductVariantResponse | null>(null);

  useEffect(() => {
    if (product && !selectedVariant) {
      const firstActive = product.variants.find((v) => v.status === "ACTIVE") ?? product.variants[0] ?? null;
      setSelectedVariant(firstActive);
    }
  }, [product, selectedVariant]);

  const stepper = useVariantStepper(selectedVariant?.id ?? -1);
  const inStock = selectedVariant?.in_stock !== false;
  const isAvailable = selectedVariant?.status === "ACTIVE" && inStock;
  const embellishment = getEmbellishment(product?.slug ?? "");

  const { data: relatedPages } = useProducts(product ? { categoryId: product.category.id } : { categoryId: -1 });
  const relatedProducts = useMemo(() => {
    const items = relatedPages?.pages.flatMap((p) => p.items) ?? [];
    return items.filter((p) => p.id !== productId).slice(0, 8).map(productSummaryToCardData);
  }, [relatedPages, productId]);

  if (isLoading || !product) {
    return (
      <Screen edges={["bottom"]}>
        <Stack.Screen options={{ headerShown: false }} />
        <View style={{ paddingTop: insets.top + spacing.base, padding: spacing.base }}>
          <Skeleton height={SCREEN_WIDTH - spacing.base * 2} borderRadius={0} />
          <View style={{ height: spacing.lg }} />
          <Skeleton height={26} width="80%" />
          <View style={{ height: spacing.md }} />
          <Skeleton height={16} width="40%" />
        </View>
      </Screen>
    );
  }

  const images = (product.images.length > 0 ? product.images : [product.images[0]]).filter(Boolean);
  const selectedSize = selectedVariant ? formatVariantSize(selectedVariant.quantity, selectedVariant.unit) : null;
  const selectedRate = selectedVariant?.current_price
    ? formatRatePerUnit(selectedVariant.current_price.price, selectedVariant.quantity, selectedVariant.unit)
    : null;
  const inCart = (stepper.quantity ?? 0) > 0;
  const infoTiles: { icon: React.ComponentProps<typeof Feather>["name"]; label: string; value: string }[] = [];
  if (embellishment.origin) infoTiles.push({ icon: "map-pin", label: "Origin", value: embellishment.origin });
  infoTiles.push({ icon: "check-circle", label: "Quality", value: "Handpicked & Graded" });
  if (embellishment.eta) infoTiles.push({ icon: "zap", label: "Delivery", value: `In ${embellishment.eta.toLowerCase()}` });

  const stepperProps = {
    quantity: stepper.quantity ?? 0,
    disabled: !isAvailable || stepper.isMutating,
    onAdd: () => stepper.add(),
    onIncrement: stepper.increment,
    onDecrement: stepper.decrement,
  };

  return (
    <Screen edges={["bottom"]}>
      <Stack.Screen options={{ headerShown: false }} />
      <ScrollView showsVerticalScrollIndicator={false} bounces={false}>
        <View style={styles.galleryWrap}>
          <ScrollView
            horizontal
            pagingEnabled
            showsHorizontalScrollIndicator={false}
            onMomentumScrollEnd={(e) => {
              setActiveImage(Math.round(e.nativeEvent.contentOffset.x / SCREEN_WIDTH));
            }}
          >
            {images.map((img, idx) => (
              <Image
                key={img?.id ?? idx}
                source={img?.image_url}
                style={{ width: SCREEN_WIDTH, height: IMAGE_HEIGHT, backgroundColor: colors.divider }}
                contentFit="cover"
                transition={250}
              />
            ))}
          </ScrollView>

          <Pressable
            onPress={() => router.back()}
            style={[styles.roundButton, { top: insets.top + spacing.sm, left: spacing.base }]}
            accessibilityRole="button"
            accessibilityLabel="Go back"
            hitSlop={8}
          >
            <Feather name="arrow-left" size={22} color={colors.primary} />
          </Pressable>

          <View style={[styles.heartWrap, { top: insets.top + spacing.sm }]}>
            <WishlistButton productId={productId} size={24} />
            <Pressable
              onPress={() => Share.share({ message: `${product.name} on Gawacha Bazaar` }).catch(() => undefined)}
              style={styles.shareButton}
              accessibilityRole="button"
              accessibilityLabel="Share"
              hitSlop={8}
            >
              <Feather name="share-2" size={22} color={colors.textPrimary} />
            </Pressable>
          </View>

          {images.length > 1 ? (
            <>
              <View style={styles.dots}>
                {images.map((img, idx) => (
                  <View key={img?.id ?? idx} style={[styles.dot, idx === activeImage && styles.dotActive]} />
                ))}
              </View>
              <View style={styles.counterBadge}>
                <Text variant="bodyMedium" color={colors.textInverse}>
                  {activeImage + 1}/{images.length}
                </Text>
              </View>
            </>
          ) : null}
        </View>

        <Animated.View entering={FadeInUp.duration(280)} style={styles.content}>
          <View style={styles.pillRow}>
            <View style={styles.categoryPill}>
              <Ionicons name="apps" size={15} color={colors.accentDark} />
              <Text variant="bodyMedium" color={colors.primary}>
                {product.category.name.toUpperCase()}
              </Text>
            </View>
            <View style={styles.categoryPill}>
              <Ionicons name="leaf" size={15} color={colors.brandGreen} />
              <Text variant="bodyMedium" color={colors.primary}>
                Fresh &amp; Natural
              </Text>
            </View>
          </View>

          <Text variant="displayM" style={styles.name}>
            {displayName(product.name)}
          </Text>
          {embellishment.marathiName ? (
            <Text variant="script" color={colors.textSecondary}>
              {embellishment.marathiName}
            </Text>
          ) : null}

          <View style={styles.priceRow}>
            <View style={styles.priceLeft}>
              <View style={styles.priceLine}>
                {selectedVariant?.current_price ? (
                  <PriceTag amount={selectedVariant.current_price.price} currency={selectedVariant.current_price.currency} mrp={embellishment.mrp} size="lg" />
                ) : (
                  <Text variant="body" color={colors.textMuted}>
                    Price unavailable
                  </Text>
                )}
                {selectedSize ? (
                  <View style={styles.sizePill}>
                    <Text variant="bodyMedium" color={colors.textSecondary}>
                      {selectedSize}
                    </Text>
                  </View>
                ) : null}
              </View>
              {selectedRate ? (
                <Text variant="body" color={colors.textMuted} style={styles.rate}>
                  {selectedRate.replace("/", " per ")}
                </Text>
              ) : null}
              {!isAvailable ? (
                <View style={styles.unavailableBadge}>
                  <Text variant="captionMedium" color={colors.error}>
                    {selectedVariant?.status === "ACTIVE" && !inStock ? "Out of stock" : "Currently unavailable"}
                  </Text>
                </View>
              ) : null}
            </View>
            <PillStepper {...stepperProps} />
          </View>

          {product.variants.length > 0 ? (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.variantScroll}>
              {product.variants.map((variant) => {
                const active = variant.id === selectedVariant?.id;
                const soldOut = variant.in_stock === false;
                return (
                  <Pressable
                    key={variant.id}
                    onPress={() => setSelectedVariant(variant)}
                    disabled={variant.status !== "ACTIVE"}
                    accessibilityRole="button"
                    accessibilityState={{ selected: active }}
                    style={[styles.variantCard, active && styles.variantCardActive, soldOut && styles.variantCardSoldOut]}
                  >
                    <Text variant="bodyMedium" color={colors.textPrimary}>
                      {formatVariantSize(variant.quantity, variant.unit)}
                    </Text>
                    <Text variant="price" color={colors.price}>
                      {variant.current_price ? formatMoney(variant.current_price.price, variant.current_price.currency) : "—"}
                    </Text>
                    {soldOut ? (
                      <Text variant="captionMedium" color={colors.error}>
                        Out of stock
                      </Text>
                    ) : null}
                    {active ? (
                      <View style={styles.variantCheck}>
                        <Feather name="check" size={11} color={colors.textInverse} />
                      </View>
                    ) : null}
                  </Pressable>
                );
              })}
            </ScrollView>
          ) : null}

          {product.description ? (
            <View style={styles.descriptionCard}>
              <View style={styles.descriptionTitle}>
                <Ionicons name="leaf" size={22} color={colors.brandGreen} />
                <Text variant="h2">Description</Text>
              </View>
              <Text variant="bodyLarge" color={colors.textSecondary} style={styles.descriptionBody}>
                {product.description}
              </Text>
            </View>
          ) : null}

          <View style={styles.tileRow}>
            {infoTiles.map((tile) => (
              <View key={tile.label} style={styles.tile}>
                <Feather name={tile.icon} size={18} color={colors.accentDark} />
                <Text variant="captionMedium" color={colors.textMuted}>
                  {tile.label}
                </Text>
                <Text variant="bodySmall" color={colors.textSecondary}>
                  {tile.value}
                </Text>
              </View>
            ))}
          </View>
        </Animated.View>

        {relatedProducts.length > 0 ? (
          <View style={styles.relatedWrap}>
            <View style={styles.relatedHeader}>
              <Text variant="h2">You may also like</Text>
              <Pressable onPress={() => router.push(`/category/${product.category.id}`)} hitSlop={8}>
                <Text variant="bodyMedium" color={colors.accentDark}>
                  See all →
                </Text>
              </Pressable>
            </View>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.relatedScroll}>
              {relatedProducts.map((p, i) => (
                <View key={p.id} style={{ width: 158 }}>
                  <ProductCard product={p} onPress={() => router.push(`/product/${p.id}`)} index={i} />
                </View>
              ))}
            </ScrollView>
          </View>
        ) : null}
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: insets.bottom + spacing.sm }]}>
        <Image source={images[0]?.image_url} style={styles.footerThumb} contentFit="cover" />
        <View style={styles.footerInfo}>
          <Text variant="h3" numberOfLines={1}>
            {displayName(product.name)}
          </Text>
          <Text variant="bodySmall" color={colors.textMuted} numberOfLines={1}>
            {[selectedSize, selectedRate?.replace("/", " per ")].filter(Boolean).join(" • ")}
          </Text>
        </View>
        <PillStepper {...stepperProps} small />
        <Pressable
          disabled={!isAvailable || stepper.isMutating}
          onPress={() => (inCart ? router.push("/cart") : stepper.add())}
          style={[styles.cartButton, (!isAvailable || stepper.isMutating) && styles.disabled]}
          accessibilityRole="button"
          accessibilityLabel={inCart ? "Go to cart" : "Add to cart"}
        >
          <Feather name="shopping-cart" size={22} color={colors.textInverse} />
          <View>
            <Text variant="button" color={colors.textInverse}>
              {inCart ? "Go to Cart" : "Add to Cart"}
            </Text>
            {selectedVariant?.current_price ? (
              <Text variant="captionMedium" color={colors.textInverse}>
                {formatMoney(selectedVariant.current_price.price, selectedVariant.current_price.currency)}
              </Text>
            ) : null}
          </View>
        </Pressable>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  heartWrap: { position: "absolute", right: spacing.base, flexDirection: "row", gap: spacing.md },
  shareButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(255,255,255,0.92)",
    alignItems: "center",
    justifyContent: "center",
  },
  galleryWrap: { position: "relative" },
  roundButton: {
    position: "absolute",
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  dots: {
    position: "absolute",
    bottom: spacing["2xl"],
    alignSelf: "center",
    flexDirection: "row",
    gap: 8,
  },
  dot: { width: 10, height: 10, borderRadius: 5, borderWidth: 1, borderColor: colors.textInverse },
  dotActive: { backgroundColor: colors.textInverse },
  counterBadge: {
    position: "absolute",
    right: spacing.base,
    bottom: spacing["2xl"],
    backgroundColor: "rgba(11, 45, 32, 0.55)",
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: 999,
  },
  // Overlaps the photo so the sheet reads as a rounded card rising over it.
  content: {
    padding: spacing.base,
    paddingTop: spacing.lg,
    marginTop: -spacing.xl,
    backgroundColor: colors.background,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
  },
  pillRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  categoryPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.primaryLight,
    paddingHorizontal: spacing.base,
    paddingVertical: 8,
    borderRadius: 999,
  },
  name: { marginTop: spacing.md, fontSize: 44, lineHeight: 52, fontFamily: "BodoniModa_700Bold" },
  priceRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md, marginTop: spacing.lg },
  priceLeft: { flex: 1 },
  priceLine: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  sizePill: { backgroundColor: colors.divider, paddingHorizontal: spacing.base, paddingVertical: 6, borderRadius: 999 },
  rate: { marginTop: 6 },
  unavailableBadge: {
    alignSelf: "flex-start",
    marginTop: spacing.sm,
    backgroundColor: colors.errorLight,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radius.card,
  },
  disabled: { opacity: 0.4 },
  pillStepper: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    height: 56,
    paddingLeft: spacing.base,
    paddingRight: 6,
    borderRadius: 999,
    borderWidth: 1.5,
    borderColor: colors.borderStrong,
    backgroundColor: colors.surface,
  },
  pillStepperSmall: { height: 46, gap: spacing.sm, paddingLeft: spacing.md, paddingRight: 5 },
  pillMinus: { alignItems: "center", justifyContent: "center" },
  pillCount: { minWidth: 18, textAlign: "center" },
  pillPlus: { backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },
  variantScroll: { gap: spacing.md, paddingTop: spacing.lg },
  variantCard: {
    minWidth: 104,
    padding: spacing.md,
    gap: 2,
    alignItems: "center",
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  variantCardActive: { borderColor: colors.primary, backgroundColor: colors.surfaceTint },
  variantCardSoldOut: { opacity: 0.5 },
  variantCheck: {
    position: "absolute",
    top: 6,
    right: 6,
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  descriptionCard: {
    marginTop: spacing.lg,
    padding: spacing.base,
    borderRadius: 20,
    backgroundColor: colors.surfaceTint,
  },
  descriptionTitle: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  descriptionBody: { marginTop: spacing.sm },
  tileRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.lg },
  tile: {
    flex: 1,
    gap: 2,
    padding: spacing.md,
    borderRadius: 16,
    backgroundColor: colors.surface,
  },
  // Extra bottom room so the footer card never covers the last row.
  relatedWrap: { marginTop: spacing.xl, paddingBottom: spacing.xl + 64 },
  relatedHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.base,
    marginBottom: spacing.base,
  },
  relatedScroll: { paddingHorizontal: spacing.base, gap: spacing.md },
  footer: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginHorizontal: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    backgroundColor: colors.surface,
  },
  footerThumb: { width: 52, height: 52, borderRadius: 14, backgroundColor: colors.divider },
  footerInfo: { flex: 1 },
  cartButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
    borderRadius: 18,
    backgroundColor: colors.primary,
  },
});
