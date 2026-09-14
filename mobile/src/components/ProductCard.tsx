import React from "react";
import { StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { Feather } from "@expo/vector-icons";
import Animated, { FadeInUp } from "react-native-reanimated";
import { Text } from "./Text";
import { PriceTag } from "./PriceTag";
import { QuantityStepper } from "./QuantityStepper";
import { PressableScale } from "./PressableScale";
import { useVariantStepper } from "@/features/cart/useCart";
import { formatVariantSize } from "@/utils/money";
import { getEmbellishment } from "@/utils/productEmbellishments";
import { colors, radius, shadows, spacing } from "@/theme";
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
  const stepper = useVariantStepper(addableVariantId ?? -1);
  const isAvailable = addableVariantId !== null;
  const price = product.variant?.current_price ?? product.startingPrice ?? null;
  const { marathiName, origin, mrp, badge, eta } = getEmbellishment(product.slug);

  return (
    <Animated.View entering={FadeInUp.delay(Math.min(index, 8) * 40).duration(280)}>
      <PressableScale onPress={onPress} style={styles.card} accessibilityRole="button" accessibilityLabel={product.name}>
        <View style={styles.imageWrap}>
          <Image
            source={product.imageUrl ?? undefined}
            style={styles.image}
            contentFit="cover"
            transition={200}
            placeholder={{ blurhash: "L4C~D%~q00~q~q00%M-;9F%M-;-;" }}
          />
          {badge ? (
            <View style={styles.badge}>
              <Text variant="label" color={colors.textOnAccent}>
                {badge}
              </Text>
            </View>
          ) : null}
          {!isAvailable ? (
            <View style={styles.unavailableOverlay}>
              <Text variant="captionMedium" color={colors.textInverse}>
                Unavailable
              </Text>
            </View>
          ) : null}
        </View>

        <View style={styles.info}>
          {origin || eta ? (
            <View style={styles.metaRow}>
              {origin ? (
                <Text variant="label" color={colors.accentDark} numberOfLines={1} style={styles.origin}>
                  {origin.toUpperCase()}
                </Text>
              ) : null}
              {eta ? (
                <View style={styles.etaFlag}>
                  <Feather name="zap" size={9} color={colors.primaryDark} />
                  <Text variant="label" color={colors.primaryDark}>
                    {eta}
                  </Text>
                </View>
              ) : null}
            </View>
          ) : null}
          <Text variant="titleSmall" numberOfLines={1} style={styles.name}>
            {product.name}
            {marathiName ? <Text variant="caption" color={colors.textSecondary}> ({marathiName})</Text> : null}
          </Text>
          {product.variant ? (
            <Text variant="caption" color={colors.textSecondary}>
              {formatVariantSize(product.variant.quantity, product.variant.unit)}
            </Text>
          ) : product.defaultVariantUnit && product.defaultVariantQuantity ? (
            <Text variant="caption" color={colors.textSecondary}>
              {formatVariantSize(product.defaultVariantQuantity, product.defaultVariantUnit)}
            </Text>
          ) : null}
        </View>

        <View style={styles.priceRow}>
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
            quantity={stepper.quantity}
            onAdd={stepper.add}
            onIncrement={stepper.increment}
            onDecrement={stepper.decrement}
            disabled={stepper.isMutating}
            fullWidth
          />
        ) : null}
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
  };
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.divider,
    padding: spacing.md,
    ...shadows.card,
  },
  imageWrap: {
    width: "100%",
    aspectRatio: 1,
    borderRadius: radius.sm,
    overflow: "hidden",
    backgroundColor: colors.background,
  },
  image: { width: "100%", height: "100%" },
  badge: {
    position: "absolute",
    top: spacing.sm,
    left: spacing.sm,
    backgroundColor: colors.accent,
    borderRadius: radius.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  unavailableOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: colors.overlay,
    alignItems: "center",
    justifyContent: "center",
  },
  info: { marginTop: spacing.md, minHeight: 58 },
  metaRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.xs },
  origin: { flexShrink: 1 },
  etaFlag: { flexDirection: "row", alignItems: "center", gap: 2 },
  name: { marginBottom: 4 },
  priceRow: {
    marginTop: spacing.sm,
    marginBottom: spacing.md,
  },
});
