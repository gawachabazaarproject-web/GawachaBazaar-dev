import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { Text } from "./Text";
import { PriceTag } from "./PriceTag";
import { QuantityStepper } from "./QuantityStepper";
import { useVariantStepper } from "@/features/cart/useCart";
import { formatVariantSize } from "@/utils/money";
import { colors, radius, shadows, spacing } from "@/theme";
import { ProductSummaryResponse, ProductVariantResponse } from "@/types/api";

export interface ProductCardData {
  id: number;
  name: string;
  imageUrl: string | null;
  /** The single variant this card adds to cart - for the MVP a product
   * card always represents its default/first sellable variant; the full
   * variant picker lives on the product detail screen. */
  variant: ProductVariantResponse | null;
}

export interface ProductCardProps {
  product: ProductCardData;
  onPress: () => void;
}

/**
 * The one reusable product card, used on Home, Category, and Search
 * results. Deliberately restrained: image, name, pack size, price, and a
 * quantity control - hierarchy through spacing and type weight, not
 * borders or heavy shadows.
 */
export function ProductCard({ product, onPress }: ProductCardProps) {
  const stepper = useVariantStepper(product.variant?.id ?? -1);
  const isAvailable = product.variant !== null && product.variant.status === "ACTIVE";

  return (
    <Pressable onPress={onPress} style={styles.card} accessibilityRole="button" accessibilityLabel={product.name}>
      <View style={styles.imageWrap}>
        <Image
          source={product.imageUrl ?? undefined}
          style={styles.image}
          contentFit="cover"
          transition={150}
          placeholder={{ blurhash: "L4C~D%~q00~q~q00%M-;9F%M-;-;" }}
        />
        {!isAvailable ? (
          <View style={styles.unavailableOverlay}>
            <Text variant="captionMedium" color={colors.textInverse}>
              Unavailable
            </Text>
          </View>
        ) : null}
      </View>

      <View style={styles.info}>
        <Text variant="bodyMedium" numberOfLines={2} style={styles.name}>
          {product.name}
        </Text>
        {product.variant ? (
          <Text variant="caption" color={colors.textSecondary}>
            {formatVariantSize(product.variant.quantity, product.variant.unit)}
          </Text>
        ) : null}
      </View>

      <View style={styles.footer}>
        {product.variant?.current_price ? (
          <PriceTag amount={product.variant.current_price.price} currency={product.variant.current_price.currency} />
        ) : (
          <Text variant="bodySmall" color={colors.textMuted}>
            Price unavailable
          </Text>
        )}
        {isAvailable ? (
          <QuantityStepper
            quantity={stepper.quantity}
            onAdd={stepper.add}
            onIncrement={stepper.increment}
            onDecrement={stepper.decrement}
            disabled={stepper.isMutating}
          />
        ) : null}
      </View>
    </Pressable>
  );
}

/** Maps a catalog list item (no variant/price detail) into card data - used
 * on Home/Category grids where only the lightweight summary is fetched. */
export function productSummaryToCardData(product: ProductSummaryResponse): ProductCardData {
  return { id: product.id, name: product.name, imageUrl: product.primary_image_url, variant: null };
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.sm,
    ...shadows.card,
  },
  imageWrap: {
    width: "100%",
    aspectRatio: 1,
    borderRadius: radius.md,
    overflow: "hidden",
    backgroundColor: colors.divider,
  },
  image: { width: "100%", height: "100%" },
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
  info: { marginTop: spacing.sm, minHeight: 52 },
  name: { marginBottom: 2 },
  footer: {
    marginTop: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
});
