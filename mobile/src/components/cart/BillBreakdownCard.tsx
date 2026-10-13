import React, { useMemo } from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "@/components/Text";
import { formatMoney } from "@/utils/money";
import { getEmbellishment } from "@/utils/productEmbellishments";
import { colors, spacing } from "@/theme";
import { CartItemResponse } from "@/types/api";

export interface BillBreakdownCardProps {
  items: CartItemResponse[];
  totalAmount: string | null;
  currency: string | null;
  /** Backend delivery quote for the selected address; null while loading. */
  deliveryFee?: number | null;
  grandTotal?: string | null;
}

/**
 * Real subtotal/total, always. "Farm Direct Savings" is computed from
 * the illustrative per-product MRP layer (productEmbellishments.ts) -
 * items with no MRP entry simply contribute nothing to it, so the
 * number is never inflated beyond what's actually shown on-screen.
 * The delivery fee is the backend quote (free for a 15+ product Bazaar,
 * otherwise base + per-km) - the order is re-priced server-side at checkout.
 */
export function BillBreakdownCard({ items, totalAmount, currency, deliveryFee = null, grandTotal }: BillBreakdownCardProps) {
  const { mrpTotal, savings } = useMemo(() => {
    let mrp = 0;
    for (const item of items) {
      const qty = Number.parseFloat(item.quantity);
      const unitMrp = Number.parseFloat(getEmbellishment(item.product_slug).mrp ?? item.unit_price ?? "0");
      mrp += unitMrp * qty;
    }
    const total = Number.parseFloat(totalAmount ?? "0");
    return { mrpTotal: mrp, savings: Math.max(0, mrp - total) };
  }, [items, totalAmount]);

  return (
    <View style={styles.card}>
      <Text variant="h3" style={styles.title}>
        Bill Breakdown
      </Text>
      <Row label={`Item Total (${items.length} ${items.length === 1 ? "item" : "items"})`} value={formatMoney(mrpTotal > 0 ? mrpTotal : Number.parseFloat(totalAmount ?? "0"), currency ?? "INR")} />
      {savings > 0 ? <Row label="Farm Direct Savings" value={`-${formatMoney(savings, currency ?? "INR")}`} valueColor={colors.success} /> : null}
      <Row
        label="Delivery Partner Fee"
        value={deliveryFee === null ? "-" : deliveryFee > 0 ? formatMoney(deliveryFee, currency ?? "INR") : "FREE"}
        valueColor={deliveryFee === 0 ? colors.success : undefined}
      />
      <View style={styles.divider} />
      <View style={styles.totalRow}>
        <Text variant="bodyMedium">Total Amount</Text>
        <Text variant="price">{formatMoney(grandTotal ?? totalAmount ?? "0", currency ?? "INR")}</Text>
      </View>
      {savings > 0 ? (
        <Text variant="caption" color={colors.success} style={styles.savedNote}>
          Saved {formatMoney(savings, currency ?? "INR")} today
        </Text>
      ) : null}
    </View>
  );
}

function Row({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <View style={styles.row}>
      <Text variant="bodySmall" color={colors.textSecondary}>
        {label}
      </Text>
      <Text variant="priceSmall" color={valueColor ?? colors.textPrimary}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginHorizontal: spacing.base,
    marginTop: spacing.lg,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderColor: colors.divider,
  },
  title: { marginBottom: spacing.sm },
  row: { flexDirection: "row", justifyContent: "space-between", marginBottom: spacing.sm },
  divider: { height: 1, backgroundColor: colors.divider, marginVertical: spacing.sm },
  totalRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  savedNote: { marginTop: spacing.xs },
});
