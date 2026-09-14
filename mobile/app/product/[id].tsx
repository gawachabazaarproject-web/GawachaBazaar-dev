import React, { useEffect, useState } from "react";
import { Dimensions, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { Stack, useLocalSearchParams } from "expo-router";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { PriceTag } from "@/components/PriceTag";
import { QuantityStepper } from "@/components/QuantityStepper";
import { Skeleton } from "@/components/Skeleton";
import { useProduct } from "@/features/catalog/useCatalog";
import { useVariantStepper } from "@/features/cart/useCart";
import { formatVariantSize } from "@/utils/money";
import { colors, radius, spacing } from "@/theme";
import { ProductVariantResponse } from "@/types/api";

const { width: SCREEN_WIDTH } = Dimensions.get("window");

export default function ProductDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const productId = Number(id);
  const { data: product, isLoading } = useProduct(productId);

  const [selectedVariant, setSelectedVariant] = useState<ProductVariantResponse | null>(null);

  useEffect(() => {
    if (product && !selectedVariant) {
      const firstActive = product.variants.find((v) => v.status === "ACTIVE") ?? product.variants[0] ?? null;
      setSelectedVariant(firstActive);
    }
  }, [product, selectedVariant]);

  const stepper = useVariantStepper(selectedVariant?.id ?? -1);
  const isAvailable = selectedVariant?.status === "ACTIVE";

  if (isLoading || !product) {
    return (
      <Screen>
        <Stack.Screen options={{ headerShown: true, title: "" }} />
        <View style={{ padding: spacing.base }}>
          <Skeleton height={SCREEN_WIDTH - spacing.base * 2} borderRadius={radius.lg} />
          <View style={{ height: spacing.lg }} />
          <Skeleton height={22} width="80%" />
          <View style={{ height: spacing.md }} />
          <Skeleton height={16} width="40%" />
        </View>
      </Screen>
    );
  }

  const primaryImage = product.images.find((i) => i.is_primary) ?? product.images[0];

  return (
    <Screen edges={["bottom"]}>
      <Stack.Screen options={{ headerShown: true, title: "" }} />
      <ScrollView showsVerticalScrollIndicator={false}>
        <ScrollView horizontal pagingEnabled showsHorizontalScrollIndicator={false}>
          {(product.images.length > 0 ? product.images : [primaryImage]).filter(Boolean).map((img, idx) => (
            <Image
              key={img?.id ?? idx}
              source={img?.image_url}
              style={styles.image}
              contentFit="cover"
              transition={150}
            />
          ))}
        </ScrollView>

        <View style={styles.content}>
          <Text variant="caption" color={colors.textSecondary}>
            {product.category.name}
          </Text>
          <Text variant="h1" style={styles.name}>
            {product.name}
          </Text>

          {product.variants.length > 1 ? (
            <View style={styles.variantRow}>
              {product.variants.map((variant) => {
                const active = variant.id === selectedVariant?.id;
                return (
                  <Pressable
                    key={variant.id}
                    onPress={() => setSelectedVariant(variant)}
                    style={[styles.variantChip, active && styles.variantChipActive]}
                    disabled={variant.status !== "ACTIVE"}
                  >
                    <Text variant="bodySmall" color={active ? colors.textInverse : colors.textPrimary}>
                      {formatVariantSize(variant.quantity, variant.unit)}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          ) : selectedVariant ? (
            <Text variant="body" color={colors.textSecondary} style={styles.singleVariant}>
              {formatVariantSize(selectedVariant.quantity, selectedVariant.unit)}
            </Text>
          ) : null}

          <View style={styles.priceRow}>
            {selectedVariant?.current_price ? (
              <PriceTag amount={selectedVariant.current_price.price} currency={selectedVariant.current_price.currency} size="lg" />
            ) : (
              <Text variant="body" color={colors.textMuted}>
                Price unavailable
              </Text>
            )}
            {!isAvailable ? (
              <View style={styles.unavailableBadge}>
                <Text variant="captionMedium" color={colors.error}>
                  Currently unavailable
                </Text>
              </View>
            ) : null}
          </View>

          {product.description ? (
            <>
              <Text variant="h3" style={styles.sectionTitle}>
                About this product
              </Text>
              <Text variant="body" color={colors.textSecondary}>
                {product.description}
              </Text>
            </>
          ) : null}
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <View style={styles.footerPrice}>
          {selectedVariant?.current_price ? (
            <PriceTag amount={selectedVariant.current_price.price} currency={selectedVariant.current_price.currency} />
          ) : null}
        </View>
        <QuantityStepper
          compact={false}
          quantity={stepper.quantity}
          disabled={!isAvailable || stepper.isMutating}
          onAdd={() => stepper.add()}
          onIncrement={stepper.increment}
          onDecrement={stepper.decrement}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  image: { width: SCREEN_WIDTH, height: SCREEN_WIDTH, backgroundColor: colors.divider },
  content: { padding: spacing.base },
  name: { marginTop: spacing.xs },
  variantRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.base },
  variantChip: {
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: 1.5,
    borderColor: colors.border,
  },
  variantChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  singleVariant: { marginTop: spacing.sm },
  priceRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginTop: spacing.lg },
  unavailableBadge: { backgroundColor: colors.errorLight, paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: radius.sm },
  sectionTitle: { marginTop: spacing.xl, marginBottom: spacing.sm },
  footer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: spacing.base,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
  },
  footerPrice: { flex: 1 },
});
