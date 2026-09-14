import React, { useMemo } from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "@/components/Text";
import { formatMoney } from "@/utils/money";
import { getEmbellishment } from "@/utils/productEmbellishments";
import { colors, radius, shadows, spacing } from "@/theme";
import { CartItemResponse } from "@/types/api";

export interface BillBreakdownCardProps {
  items: CartItemResponse[];
  totalAmount: string | null;
  currency: string | null;
}

/**
 * Real subtotal/total, always. "Farm Direct Savings" is computed from
 * the illustrative per-product MRP layer (productEmbellishments.ts) -
 * items with no MRP entry simply contribute nothing to it, so the
 * number is never inflated beyond what's actually shown on-screen.
 * "Delivery Partner Fee: FREE" is honest, not illustrative - the backend
 * genuinely never charges one.
 */
export function BillBreakdownCard({ items, totalAmount, currency }: BillBreakdownCardProps) {
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
      <Row label={`Item Total${mrpTotal > 0 ? ` (MRP ${formatMoney(mrpTotal, currency ?? "INR")})` : ""}`} value={formatMoney(totalAmount ?? "0", currency ?? "INR")} />
      {savings > 0 ? <Row label="Farm Direct Savings" value={`-${formatMoney(savings, currency ?? "INR")}`} valueColor={colors.success} /> : null}
      <Row label="Delivery Partner Fee" value="FREE" valueColor={colors.success} />
      <View style={styles.divider} />
      <View style={styles.totalRow}>
        <Text variant="bodyMedium">Total Bill Amount</Text>
        <Text variant="h3">{formatMoney(totalAmount ?? "0", currency ?? "INR")}</Text>
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
      <Text variant="body" color={colors.textSecondary}>
        {label}
      </Text>
      <Text variant="bodyMedium" color={valueColor ?? colors.textPrimary}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginHorizontal: spacing.base,
    marginTop: spacing.base,
    padding: spacing.base,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.divider,
    ...shadows.card,
  },
  title: { marginBottom: spacing.md },
  row: { flexDirection: "row", justifyContent: "space-between", marginBottom: spacing.sm },
  divider: { height: 1, backgroundColor: colors.divider, marginVertical: spacing.sm },
  totalRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  savedNote: { marginTop: spacing.xs },
});
