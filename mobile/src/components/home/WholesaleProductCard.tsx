import React, { useState } from "react";
import { Pressable, StyleSheet, TextInput, View } from "react-native";
import { Image } from "expo-image";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { Text } from "../Text";
import { PressableScale } from "../PressableScale";
import { getEmbellishment } from "@/utils/productEmbellishments";
import { useWholesaleStore } from "@/store/wholesaleStore";
import { colors, radius, shadows, spacing, typography } from "@/theme";
import { ProductCardData } from "../ProductCard";
import { RequestUnit } from "@/types/api";

const UNITS: RequestUnit[] = ["KG", "BOX", "CRATE", "DOZEN"];

export interface WholesaleProductCardProps {
  product: ProductCardData;
  onPress: () => void;
}

/**
 * Wholesale twin of ProductCard - same image/name/origin, but the
 * retail price + small stepper are replaced with a free-text quantity and
 * a unit picker, feeding a BulkOrderRequest draft (see wholesaleStore.ts)
 * rather than the cart. There is deliberately no live price here: bulk
 * pricing is quoted by ops per request (bulk_order.py), never computed
 * client-side.
 */
export function WholesaleProductCard({ product, onPress }: WholesaleProductCardProps) {
  const { origin, eta } = getEmbellishment(product.slug);
  const draftItem = useWholesaleStore((s) => s.draftItems.find((i) => i.productId === product.id));
  const addOrUpdateItem = useWholesaleStore((s) => s.addOrUpdateItem);
  const removeItem = useWholesaleStore((s) => s.removeItem);

  const [quantity, setQuantity] = useState(draftItem?.quantity ?? "");
  const [unit, setUnit] = useState<RequestUnit>(draftItem?.unit ?? "KG");

  const handleAdd = () => {
    const trimmed = quantity.trim();
    if (!trimmed || Number.parseFloat(trimmed) <= 0) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => undefined);
    addOrUpdateItem({ productId: product.id, productName: product.name, imageUrl: product.imageUrl, quantity: trimmed, unit });
  };

  const handleRemove = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => undefined);
    removeItem(product.id);
    setQuantity("");
  };

  return (
    <PressableScale onPress={onPress} style={styles.card} accessibilityRole="button" accessibilityLabel={product.name}>
      {/* Shadow lives on `card` (PressableScale) above, corner rounding +
          clipping lives on this inner `surface` wrapper - overflow:hidden
          on the same view as a shadow would clip the shadow away. */}
      <View style={styles.surface}>
        <View style={styles.imageWrap}>
          <Image
            source={product.imageUrl ?? undefined}
            style={styles.image}
            contentFit="cover"
            transition={200}
            placeholder={{ blurhash: "L4C~D%~q00~q~q00%M-;9F%M-;-;" }}
          />
          {draftItem ? (
            <View style={styles.inBadge}>
              <Feather name="check" size={11} color={colors.textInverse} />
              <Text variant="label" color={colors.textInverse}>
                IN REQUEST
              </Text>
            </View>
          ) : null}
        </View>

        <View style={styles.body}>
          {origin || eta ? (
            <View style={styles.metaRow}>
              {origin ? (
                <Text variant="eyebrow" color={colors.accentDark} numberOfLines={1} style={{ flexShrink: 1 }}>
                  {origin.toUpperCase()}
                </Text>
              ) : null}
            </View>
          ) : null}
          <Text variant="titleSmall" numberOfLines={1} style={styles.name}>
            {product.name}
          </Text>

          <View style={styles.qtyRow}>
            <TextInput
              value={quantity}
              onChangeText={setQuantity}
              placeholder="Qty"
              placeholderTextColor={colors.textMuted}
              keyboardType="decimal-pad"
              style={styles.qtyInput}
            />
            <View style={styles.unitRow}>
              {UNITS.map((u) => (
                <Pressable key={u} onPress={() => setUnit(u)} style={[styles.unitChip, unit === u && styles.unitChipActive]}>
                  <Text variant="label" numberOfLines={1} color={unit === u ? colors.textInverse : colors.textSecondary}>
                    {u}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>

          {draftItem ? (
            <Pressable style={styles.removeButton} onPress={handleRemove} accessibilityRole="button" accessibilityLabel="Remove from request">
              <Text variant="button" color={colors.error}>
                Remove
              </Text>
            </Pressable>
          ) : (
            <Pressable style={styles.addButton} onPress={handleAdd} accessibilityRole="button" accessibilityLabel="Add to request">
              <Text variant="button" color={colors.primary}>
                Add to request
              </Text>
            </Pressable>
          )}
        </View>
      </View>
    </PressableScale>
  );
}

const styles = StyleSheet.create({
  card: { flex: 1, ...shadows.card },
  surface: { borderRadius: radius.xs, overflow: "hidden", backgroundColor: colors.surface },
  imageWrap: {
    width: "100%",
    aspectRatio: 0.82,
    overflow: "hidden",
    backgroundColor: colors.background,
  },
  image: { width: "100%", height: "100%" },
  inBadge: {
    position: "absolute",
    top: spacing.sm,
    left: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  body: { paddingHorizontal: spacing.sm, paddingBottom: spacing.sm, marginTop: spacing.base },
  metaRow: { marginBottom: spacing.sm },
  name: { marginBottom: spacing.sm },
  qtyRow: { marginTop: spacing.xs, gap: spacing.sm },
  qtyInput: {
    ...typography.bodyMedium,
    color: colors.textPrimary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.none,
    paddingHorizontal: spacing.sm,
    height: 38,
  },
  unitRow: { flexDirection: "row", gap: spacing.xs },
  unitChip: {
    flex: 1,
    height: 26,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.none,
  },
  unitChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  addButton: {
    marginTop: spacing.md,
    height: 38,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: radius.none,
  },
  removeButton: {
    marginTop: spacing.md,
    height: 38,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.error,
    borderRadius: radius.none,
  },
});
