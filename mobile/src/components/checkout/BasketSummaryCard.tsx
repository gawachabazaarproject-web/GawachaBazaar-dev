import React, { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { formatMoney } from "@/utils/money";
import { colors, spacing } from "@/theme";
import { CartItemResponse } from "@/types/api";

export interface BasketSummaryCardProps {
  items: CartItemResponse[];
  totalAmount: string | null;
  currency: string | null;
}

/** Collapsible order-items summary - real cart items/prices, expand
 * state only (no fabricated content). */
export function BasketSummaryCard({ items, totalAmount, currency }: BasketSummaryCardProps) {
  const [expanded, setExpanded] = useState(true);

  return (
    <View style={styles.card}>
      <Pressable style={styles.header} onPress={() => setExpanded((v) => !v)}>
        <Text variant="bodyMedium" style={{ flex: 1 }}>
          {items.length} {items.length === 1 ? "item" : "items"} in this order
        </Text>
        <Text variant="bodyMedium">{formatMoney(totalAmount ?? "0", currency ?? "INR")}</Text>
        <Feather name={expanded ? "chevron-up" : "chevron-down"} size={16} color={colors.textSecondary} style={{ marginLeft: spacing.xs }} />
      </Pressable>
      {expanded ? (
        <>
          <View style={styles.divider} />
          {items.map((item) => (
            <View key={item.id} style={styles.row}>
              <Text variant="body" style={{ flex: 1 }} numberOfLines={1}>
                {item.product_name} ({item.variant_name})
              </Text>
              <Text variant="bodyMedium">{item.line_total ? formatMoney(item.line_total, item.currency ?? "INR") : "-"}</Text>
            </View>
          ))}
          <View style={styles.divider} />
          <View style={styles.row}>
            <Text variant="body" color={colors.textSecondary}>
              Items Subtotal
            </Text>
            <Text variant="bodyMedium">{formatMoney(totalAmount ?? "0", currency ?? "INR")}</Text>
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
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center" },
  divider: { height: 1, backgroundColor: colors.divider, marginVertical: spacing.sm },
  row: { flexDirection: "row", justifyContent: "space-between", marginBottom: spacing.sm },
});
