import React from "react";
import { StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { Feather } from "@expo/vector-icons";
import Animated, { FadeInUp } from "react-native-reanimated";
import { Text } from "./Text";
import { PriceTag } from "./PriceTag";
import { QuantityStepper } from "./QuantityStepper";
import { PressableScale } from "./PressableScale";
import { WishlistButton } from "./WishlistButton";
import { useVariantStepper } from "@/features/cart/useCart";
import { formatVariantSize } from "@/utils/money";
import { getEmbellishment } from "@/utils/productEmbellishments";
import { colors, fontFamily, shadows, spacing } from "@/theme";
import { PriceResponse, ProductSummaryResponse, ProductVariantResponse } from "@/types/api";

export interface ProductCardData {
  id: number;
  slug: string;
  name: string;
  imageUrl: string | null;
  /** The single variant this card adds to cart - for the MVP a product
   * card always represents its default/first sellable variant; the full
   * variant picker lives on the product detail screen. */
  variant: ProductVariantResponse | null;
  /** Lightweight price shown when only a catalog-list summary is
   * available (Home/Category/Search) - see `starting_price` on
   * ProductSummaryResponse. Ignored once `variant.current_price` exists. */
  startingPrice?: PriceResponse | null;
  /** The variant Add-to-cart targets when only a catalog-list summary is
   * available (no full `variant` object yet) - see `default_variant_id`
   * on ProductSummaryResponse. Ignored once `variant` is set. */
  defaultVariantId?: number | null;
  /** Pack size shown when only a catalog-list summary is available - see
   * `default_variant_unit`/`default_variant_quantity` on
   * ProductSummaryResponse. Ignored once `variant` is set. */
  defaultVariantUnit?: string | null;
  defaultVariantQuantity?: string | null;
  /** False when sold out (greyed out, cannot be added). Undefined = in stock. */
  inStock?: boolean;
}

export interface ProductCardProps {
  product: ProductCardData;
  onPress: () => void;
  /** Position within its grid - staggers the entrance animation slightly
   * so a screenful of cards doesn't pop in as one flat block. */
  index?: number;
}

/**
 * The one reusable product card, used on Home, Category, and Search
 * results. Real data (name, image, price, stock, cart state) always
 * comes from the backend; origin/Marathi-name/MRP-discount badges are an
 * explicitly-authorized illustrative layer (see productEmbellishments.ts)
 * looked up by slug and rendered only when present - never fabricated
 * for a product with no entry.
 */
export function ProductCard({ product, onPress, index = 0 }: ProductCardProps) {
  const addableVariantId = product.variant
    ? product.variant.status === "ACTIVE"
      ? product.variant.id
      : null
    : (product.defaultVariantId ?? null);
  const inStock = product.variant ? product.variant.in_stock !== false : product.inStock !== false;
  const isActive = addableVariantId !== null;
  const isAvailable = isActive && inStock;
  const price = product.variant?.current_price ?? product.startingPrice ?? null;
  const { origin, mrp, badge } = getEmbellishment(product.slug);
  const tag = badge ?? origin ?? "Farm Fresh";
  const sizeLabel = product.variant
    ? formatVariantSize(product.variant.quantity, product.variant.unit)
    : product.defaultVariantUnit && product.defaultVariantQuantity
      ? formatVariantSize(product.defaultVariantQuantity, product.defaultVariantUnit)
      : null;
  const stepper = useVariantStepper(addableVariantId ?? -1, {
    product_id: product.id,
    product_slug: product.slug,
    primary_image_url: product.imageUrl,
    product_name: product.name,
    variant_name: sizeLabel ?? "",
    sku: "",
    unit_price: price?.price ?? null,
    currency: price?.currency ?? null,
  });

  return (
    <Animated.View style={{ flex: 1 }} entering={FadeInUp.delay(Math.min(index, 8) * 40).duration(280)}>
      <PressableScale onPress={onPress} style={styles.card} accessibilityRole="button" accessibilityLabel={product.name}>
        {/* Shadow lives on `card` (PressableScale) above, corner rounding +
            clipping lives on this inner `surface` wrapper below - an
            RN gotcha: overflow:hidden on the same view as a shadow clips
            the shadow itself away, so the two responsibilities can't share
            one view. */}
        <View style={[styles.surface, !inStock && styles.soldOut]}>
          <View style={styles.imageWrap}>
            <Image
              source={product.imageUrl ?? undefined}
              style={styles.image}
              contentFit="cover"
              transition={200}
              placeholder={{ blurhash: "L4C~D%~q00~q~q00%M-;9F%M-;-;" }}
            />
            {tag ? (
              <View style={styles.badge}>
                <Feather name="feather" size={12} color={colors.primary} />
                <Text variant="label" color={colors.primaryDark} numberOfLines={1} style={styles.badgeText}>
                  {tag.toUpperCase()}
                </Text>
              </View>
            ) : null}
            <View style={styles.heart}>
              <WishlistButton productId={product.id} size={18} />
            </View>
            {!isAvailable ? (
              <View style={styles.unavailableOverlay}>
                <Text variant="captionMedium" color={colors.textInverse}>
                  {isActive ? "Out of stock" : "Unavailable"}
                </Text>
              </View>
            ) : null}
          </View>

          <Text variant="bodyMedium" color={colors.primary} numberOfLines={1} style={styles.name}>
            {product.name}
          </Text>
          <View style={styles.footer}>
            <View style={styles.footerInfo}>
              {sizeLabel ? (
                <Text variant="caption" color={colors.textSecondary}>
                  {sizeLabel}
                </Text>
              ) : null}
              {price ? (
                <PriceTag amount={price.price} currency={price.currency} mrp={mrp} />
              ) : (
                <Text variant="bodySmall" color={colors.textMuted}>
                  Price unavailable
                </Text>
              )}
            </View>
            {isAvailable ? (
              <QuantityStepper
                pill
                quantity={stepper.quantity}
                onAdd={stepper.add}
                onIncrement={stepper.increment}
                onDecrement={stepper.decrement}
                disabled={stepper.isMutating}
              />
            ) : (
              <View style={styles.soldOutPill}>
                <Text variant="captionMedium" color={colors.textMuted}>
                  Sold out
                </Text>
              </View>
            )}
          </View>
        </View>
      </PressableScale>
    </Animated.View>
  );
}

/** Maps a catalog list item (name/image/starting price - no full variant
 * detail) into card data - used on Home/Category/Search grids where only
 * the lightweight summary is fetched. */
export function productSummaryToCardData(product: ProductSummaryResponse): ProductCardData {
  return {
    id: product.id,
    slug: product.slug,
    name: product.name,
    imageUrl: product.primary_image_url,
    variant: null,
    startingPrice: product.starting_price,
    defaultVariantId: product.default_variant_id,
    defaultVariantUnit: product.default_variant_unit,
    defaultVariantQuantity: product.default_variant_quantity,
    inStock: product.in_stock !== false,
  };
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    ...shadows.card,
  },
  // Corner rounding + clipping live on `surface`, separate from `card`
  // (shadow) - overflow:hidden on a shadowed view clips the shadow away.
  surface: {
    borderRadius: 20,
    overflow: "hidden",
    backgroundColor: colors.surface,
    padding: spacing.sm,
    flex: 1,
  },
  // Sold out: the whole card fades to grey and cannot be added.
  soldOut: { opacity: 0.55 },
  soldOutPill: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.divider,
    backgroundColor: colors.background,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  imageWrap: {
    width: "100%",
    aspectRatio: 1.25,
    borderRadius: 16,
    overflow: "hidden",
    backgroundColor: colors.background,
  },
  image: { width: "100%", height: "100%" },
  badge: {
    position: "absolute",
    top: spacing.sm,
    left: spacing.sm,
    maxWidth: "70%",
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "rgba(255,255,255,0.92)",
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  badgeText: { flexShrink: 1 },
  heart: { position: "absolute", top: spacing.sm, right: spacing.sm, zIndex: 2 },
  unavailableOverlay: {
    ...StyleSheet.absoluteFill as object,
    backgroundColor: colors.overlay,
    alignItems: "center",
    justifyContent: "center",
  },
  name: { marginTop: spacing.sm, paddingHorizontal: 2, fontFamily: fontFamily.devanagari, fontSize: 17, lineHeight: 23, letterSpacing: 0.2 },
  footer: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    marginTop: "auto",
    paddingTop: 2,
    paddingHorizontal: 2,
    gap: spacing.xs,
  },
  footerInfo: { flexShrink: 1 },
});
