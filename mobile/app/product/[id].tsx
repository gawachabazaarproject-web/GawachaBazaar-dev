import React, { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, useWindowDimensions, View } from "react-native";
import { Image } from "expo-image";
import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import Animated, { FadeInUp } from "react-native-reanimated";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { PriceTag } from "@/components/PriceTag";
import { QuantityStepper } from "@/components/QuantityStepper";
import { Skeleton } from "@/components/Skeleton";
import { ProductCard, productSummaryToCardData } from "@/components/ProductCard";
import { useProduct, useProducts } from "@/features/catalog/useCatalog";
import { useVariantStepper } from "@/features/cart/useCart";
import { formatVariantSize } from "@/utils/money";
import { getEmbellishment } from "@/utils/productEmbellishments";
import { colors, radius, spacing } from "@/theme";
import { ProductVariantResponse } from "@/types/api";

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
  const isAvailable = selectedVariant?.status === "ACTIVE";
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
            style={[styles.backButton, { top: insets.top + spacing.sm }]}
            accessibilityRole="button"
            accessibilityLabel="Go back"
            hitSlop={8}
          >
            <Feather name="arrow-left" size={18} color={colors.textInverse} />
          </Pressable>

          {images.length > 1 ? (
            <View style={styles.counterBadge}>
              <Text variant="eyebrow" color={colors.textInverse}>
                {String(activeImage + 1).padStart(2, "0")} / {String(images.length).padStart(2, "0")}
              </Text>
            </View>
          ) : null}
        </View>

        <Animated.View entering={FadeInUp.duration(280)} style={styles.content}>
          <View style={styles.eyebrowRow}>
            <Text variant="eyebrow" color={colors.accentDark}>
              01 / PRODUCT
            </Text>
            <Text variant="eyebrow" color={colors.textMuted}>
              {product.category.name.toUpperCase()}
            </Text>
          </View>

          <Text variant="displayM" style={styles.name}>
            {product.name}
            {embellishment.marathiName ? (
              <Text variant="script" color={colors.textSecondary}>
                {"  "}
                {embellishment.marathiName}
              </Text>
            ) : null}
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
              <PriceTag amount={selectedVariant.current_price.price} currency={selectedVariant.current_price.currency} mrp={embellishment.mrp} size="lg" />
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

          <View style={styles.divider} />

          {embellishment.origin ? (
            <View style={styles.infoBlock}>
              <Text variant="eyebrow" color={colors.accentDark}>
                ORIGIN
              </Text>
              <Text variant="body" color={colors.textSecondary} style={styles.infoBody}>
                Sourced directly from {embellishment.origin} - hand-graded at the source, no
                middlemen in between.
              </Text>
            </View>
          ) : null}

          {embellishment.eta ? (
            <View style={styles.infoBlock}>
              <Text variant="eyebrow" color={colors.accentDark}>
                FRESHNESS
              </Text>
              <View style={styles.freshnessRow}>
                <Feather name="zap" size={13} color={colors.primary} />
                <Text variant="body" color={colors.textSecondary}>
                  Delivered in {embellishment.eta.toLowerCase()} from the nearest hub.
                </Text>
              </View>
            </View>
          ) : null}

          {product.description ? (
            <View style={styles.infoBlock}>
              <Text variant="eyebrow" color={colors.accentDark}>
                DESCRIPTION
              </Text>
              <Text variant="body" color={colors.textSecondary} style={styles.infoBody}>
                {product.description}
              </Text>
            </View>
          ) : null}
        </Animated.View>

        {relatedProducts.length > 0 ? (
          <View style={styles.relatedWrap}>
            <Text variant="eyebrow" color={colors.accentDark} style={styles.relatedEyebrow}>
              YOU MAY ALSO LIKE
            </Text>
            <Text variant="h2" style={styles.relatedTitle}>
              Related products
            </Text>
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
  galleryWrap: { position: "relative" },
  backButton: {
    position: "absolute",
    left: spacing.base,
    width: 36,
    height: 36,
    borderRadius: radius.none,
    backgroundColor: "rgba(11, 45, 32, 0.55)",
    alignItems: "center",
    justifyContent: "center",
  },
  counterBadge: {
    position: "absolute",
    right: spacing.base,
    bottom: spacing.base,
    backgroundColor: "rgba(11, 45, 32, 0.55)",
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  content: { padding: spacing.base, paddingTop: spacing.xl },
  eyebrowRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  name: { marginTop: spacing.sm },
  variantRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.lg },
  variantChip: {
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    borderRadius: radius.none,
    borderWidth: 1,
    borderColor: colors.border,
  },
  variantChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  singleVariant: { marginTop: spacing.sm },
  priceRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginTop: spacing.lg },
  unavailableBadge: { backgroundColor: colors.errorLight, paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: radius.none },
  divider: { height: 1, backgroundColor: colors.divider, marginTop: spacing.xl },
  infoBlock: { marginTop: spacing.xl },
  infoBody: { marginTop: spacing.sm, maxWidth: "94%" },
  freshnessRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.sm },
  relatedWrap: { marginTop: spacing["2xl"], paddingBottom: spacing.xl },
  relatedEyebrow: { paddingHorizontal: spacing.base },
  relatedTitle: { paddingHorizontal: spacing.base, marginTop: spacing.xs, marginBottom: spacing.base },
  relatedScroll: { paddingHorizontal: spacing.base, gap: spacing.md },
  footer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.base,
    paddingTop: spacing.base,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
  },
  footerPrice: { flex: 1 },
});
