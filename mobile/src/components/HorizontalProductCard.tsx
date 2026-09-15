import React from "react";
import { StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { PressableScale } from "./PressableScale";
import { Text } from "./Text";
import { PriceTag } from "./PriceTag";
import { QuantityStepper } from "./QuantityStepper";
import { useVariantStepper } from "@/features/cart/useCart";
import { formatVariantSize } from "@/utils/money";
import { getEmbellishment } from "@/utils/productEmbellishments";
import { colors, radius, spacing } from "@/theme";
import { ProductCardData } from "./ProductCard";

export interface HorizontalProductCardProps {
  product: ProductCardData;
  onPress: () => void;
}

/** Wide horizontal card (image left, info right, full stepper) - used for
 * "Vidarbha Regional Specialties" style rails where each item deserves
 * more presence than a compact mini-tile. Real product/price/cart state;
 * origin/Marathi name are the same illustrative layer used everywhere
 * else. */
export function HorizontalProductCard({ product, onPress }: HorizontalProductCardProps) {
  const addableVariantId = product.defaultVariantId ?? null;
  const stepper = useVariantStepper(addableVariantId ?? -1);
  const isAvailable = addableVariantId !== null;
  const { marathiName, origin } = getEmbellishment(product.slug);

  return (
    <PressableScale style={styles.card} onPress={onPress}>
      <Image
        source={product.imageUrl ?? undefined}
        style={styles.image}
        contentFit="cover"
        transition={150}
        placeholder={{ blurhash: "L4C~D%~q00~q~q00%M-;9F%M-;-;" }}
      />
      <View style={styles.info}>
        {origin ? (
          <Text variant="label" color={colors.accentDark} numberOfLines={1}>
            {origin.toUpperCase()}
          </Text>
        ) : null}
        <Text variant="titleSmall" numberOfLines={1}>
          {product.name}
          {marathiName ? <Text variant="caption" color={colors.textSecondary}> ({marathiName})</Text> : null}
        </Text>
        {product.defaultVariantUnit && product.defaultVariantQuantity ? (
          <Text variant="caption" color={colors.textSecondary} numberOfLines={1}>
            {formatVariantSize(product.defaultVariantQuantity, product.defaultVariantUnit)}
          </Text>
        ) : null}
        <View style={styles.footer}>
          {product.startingPrice ? (
            <PriceTag amount={product.startingPrice.price} currency={product.startingPrice.currency} size="md" />
          ) : null}
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
      </View>
    </PressableScale>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderColor: colors.divider,
    paddingVertical: spacing.md,
    marginHorizontal: spacing.base,
    gap: spacing.md,
  },
  image: { width: 88, height: 88, borderRadius: radius.xs, backgroundColor: colors.background },
  info: { flex: 1, justifyContent: "center", gap: 2 },
  footer: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.sm },
});
