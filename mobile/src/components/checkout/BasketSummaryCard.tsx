import React, { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { formatMoney } from "@/utils/money";
import { colors, spacing } from "@/theme";
import { CartItemResponse } from "@/types/api";

export interface BasketSummaryCardProps {
  items: CartItemResponse[];
  totalAmount: string | null;
  currency: string | null;
  slotLabel: string;
  paymentLabel: string;
}

/** Collapsible order summary - real cart items/prices. Expanded: item
 * rows with thumbnails and subtotal; collapsed: delivery slot and payment
 * method at a glance. */
export function BasketSummaryCard({ items, totalAmount, currency, slotLabel, paymentLabel }: BasketSummaryCardProps) {
  const [expanded, setExpanded] = useState(true);
  const cur = currency ?? "INR";

  return (
    <View style={styles.card}>
      <Pressable style={styles.header} onPress={() => setExpanded((v) => !v)} accessibilityRole="button">
        <View style={styles.bagCircle}>
          <Feather name="shopping-bag" size={18} color={colors.primary} />
        </View>
        <Text variant="bodyMedium" style={styles.headerText}>
          {items.length} {items.length === 1 ? "item" : "items"} in this order
        </Text>
        {expanded ? (
          <Text variant="price" style={styles.headerTotal}>
            {formatMoney(totalAmount ?? "0", cur)}
          </Text>
        ) : null}
        <Feather name={expanded ? "chevron-up" : "chevron-right"} size={18} color={colors.textPrimary} />
      </Pressable>

      {expanded ? (
        <>
          <View style={styles.divider} />
          {items.map((item, i) => (
            <View key={item.id} style={[styles.itemRow, i > 0 && styles.itemRowBorder]}>
              <Image source={item.primary_image_url ?? undefined} style={styles.thumb} contentFit="cover" />
              <View style={{ flex: 1 }}>
                <Text variant="bodyMedium" numberOfLines={1}>
                  {item.product_name}
                </Text>
                <Text variant="caption" color={colors.textSecondary}>
                  {item.variant_name}
                </Text>
              </View>
              <Text variant="price">{item.line_total ? formatMoney(item.line_total, item.currency ?? "INR") : "-"}</Text>
            </View>
          ))}
          <View style={styles.divider} />
          <View style={styles.row}>
            <Text variant="body" color={colors.textSecondary}>
              Items Subtotal
            </Text>
            <Text variant="priceSmall">{formatMoney(totalAmount ?? "0", cur)}</Text>
          </View>
          <View style={styles.row}>
            <Text variant="body" color={colors.textSecondary}>
              Mandi Direct Delivery Fee
            </Text>
            <Text variant="bodyMedium" color={colors.success}>
              FREE
            </Text>
          </View>
        </>
      ) : (
        <>
          <View style={styles.divider} />
          <GlanceRow icon="truck" label="Delivery slot" value={slotLabel} />
          <View style={styles.divider} />
          <GlanceRow icon="credit-card" label="Payment method" value={paymentLabel} />
        </>
      )}
    </View>
  );
}

function GlanceRow({ icon, label, value }: { icon: keyof typeof Feather.glyphMap; label: string; value: string }) {
  return (
    <View style={styles.glance}>
      <Feather name={icon} size={18} color={colors.textPrimary} />
      <Text variant="bodyMedium" style={{ flex: 1 }}>
        {label}
      </Text>
      <Text variant="bodySmall" color={colors.textSecondary}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 18,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.divider,
  },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  bagCircle: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  headerText: { flex: 1 },
  headerTotal: { marginRight: spacing.xs },
  divider: { height: 1, backgroundColor: colors.divider, marginVertical: spacing.sm },
  itemRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingVertical: spacing.sm },
  itemRowBorder: { borderTopWidth: 1, borderColor: colors.divider },
  thumb: { width: 44, height: 44, borderRadius: 8, backgroundColor: colors.background },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.sm },
  glance: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingVertical: 4 },
});
