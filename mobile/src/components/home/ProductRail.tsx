import React from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { SectionHeading } from "./SectionHeading";
import { ProductCard, ProductCardData } from "../ProductCard";
import { spacing } from "@/theme";

export interface ProductRailProps {
  index?: string;
  eyebrow: string;
  title: string;
  scriptSuffix?: string;
  description?: string;
  products: ProductCardData[];
  onProductPress: (product: ProductCardData) => void;
  onSeeAll?: () => void;
  /** Swaps the retail ProductCard for a different card (e.g. the
   * wholesale request-builder card) without duplicating the rail/heading
   * layout - same product data, different action per card. */
  renderCard?: (product: ProductCardData, index: number) => React.ReactNode;
  /** Overrides the default card width - the wholesale card needs a bit
   * more room for its quantity input + 4 unit chips than the retail card. */
  cardWidth?: number;
}

const CARD_WIDTH = 158;

/** Horizontal product carousel with an editorial section heading - the
 * shared shape behind "Today's Market", "Best Sellers", etc. */
export function ProductRail({
  index,
  eyebrow,
  title,
  scriptSuffix,
  description,
  products,
  onProductPress,
  onSeeAll,
  renderCard,
  cardWidth = CARD_WIDTH,
}: ProductRailProps) {
  if (products.length === 0) return null;

  return (
    <View style={styles.wrap}>
      <SectionHeading
        index={index}
        eyebrow={eyebrow}
        title={title}
        scriptSuffix={scriptSuffix}
        description={description}
        onSeeAll={onSeeAll}
      />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        {products.map((product, i) =>
          renderCard ? (
            <View key={product.id} style={{ width: cardWidth }}>
              {renderCard(product, i)}
            </View>
          ) : (
            <View key={product.id} style={{ width: cardWidth }}>
              <ProductCard product={product} onPress={() => onProductPress(product)} index={i} />
            </View>
          ),
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: spacing.xl },
  scroll: { paddingHorizontal: spacing.base, gap: spacing.md },
});
