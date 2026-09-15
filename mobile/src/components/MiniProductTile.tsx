import React from "react";
import { StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { Feather } from "@expo/vector-icons";
import { PressableScale } from "./PressableScale";
import { Text } from "./Text";
import { formatMoney } from "@/utils/money";
import { getEmbellishment } from "@/utils/productEmbellishments";
import { useVariantStepper } from "@/features/cart/useCart";
import { colors, radius, spacing } from "@/theme";
import { ProductCardData } from "./ProductCard";

export interface MiniProductTileProps {
  product: ProductCardData;
  onPress: () => void;
}

const TILE_WIDTH = 108;

/** Compact vertical tile for tight horizontal recommendation rails
 * ("Pairs with Tomatoes", "Village Mandi Add-ons") - deliberately smaller
 * than the main grid card: just enough to identify the product, see its
 * price, and add it in one tap. Real product/price/cart state. */
export function MiniProductTile({ product, onPress }: MiniProductTileProps) {
  const addableVariantId = product.defaultVariantId ?? null;
  const stepper = useVariantStepper(addableVariantId ?? -1);
  const isAvailable = addableVariantId !== null;
  const { marathiName } = getEmbellishment(product.slug);

  return (
    <PressableScale style={styles.tile} onPress={onPress}>
      <Image
        source={product.imageUrl ?? undefined}
        style={styles.image}
        contentFit="cover"
        transition={150}
        placeholder={{ blurhash: "L4C~D%~q00~q~q00%M-;9F%M-;-;" }}
      />
      <Text variant="titleSmall" numberOfLines={1} style={styles.name}>
        {product.name}
      </Text>
      {marathiName ? (
        <Text variant="caption" color={colors.textSecondary} numberOfLines={1}>
          {marathiName}
        </Text>
      ) : null}
      <View style={styles.footer}>
        {product.startingPrice ? (
          <Text variant="priceSmall" color={colors.price}>
            {formatMoney(product.startingPrice.price, product.startingPrice.currency)}
          </Text>
        ) : null}
        {isAvailable ? (
          <PressableScale
            style={styles.addButton}
            onPress={stepper.quantity ? stepper.increment : stepper.add}
            disabled={stepper.isMutating}
            hapticStyle={null}
          >
            {stepper.quantity ? (
              <Text variant="captionMedium" color={colors.textInverse}>
                {stepper.quantity}
              </Text>
            ) : (
              <Feather name="plus" size={13} color={colors.textInverse} />
            )}
          </PressableScale>
        ) : null}
      </View>
    </PressableScale>
  );
}

const styles = StyleSheet.create({
  tile: { width: TILE_WIDTH },
  image: { width: TILE_WIDTH, height: TILE_WIDTH, borderRadius: radius.xs, backgroundColor: colors.background },
  name: { marginTop: spacing.sm },
  footer: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.xs },
  addButton: {
    width: 22,
    height: 22,
    borderRadius: radius.pill,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
});
