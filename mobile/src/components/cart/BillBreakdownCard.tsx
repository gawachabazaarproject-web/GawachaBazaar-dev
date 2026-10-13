import React, { useMemo } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Text } from "@/components/Text";
import { formatMoney } from "@/utils/money";
import { getEmbellishment } from "@/utils/productEmbellishments";
import { colors, spacing } from "@/theme";
import { CartItemResponse, DeliveryQuote } from "@/types/api";
import { distanceLabel, withDelivery } from "@/utils/delivery";

export interface BillBreakdownCardProps {
  items: CartItemResponse[];
  totalAmount: string | null;
  currency: string | null;
  /** Delivery quote for the selected address; undefined while loading. */
  delivery?: DeliveryQuote;
  deliveryLoading?: boolean;
  onPinLocation?: () => void;
}

/**
 * Real subtotal/total, always. "Farm Direct Savings" is computed from
 * the illustrative per-product MRP layer (productEmbellishments.ts) -
 * items with no MRP entry simply contribute nothing to it, so the
 * number is never inflated beyond what's actually shown on-screen.
 * The delivery fee is the backend's own quote (base + per km by road to the
 * selected address) - the same number checkout will charge.
 */
export function BillBreakdownCard({ items, totalAmount, currency, delivery, deliveryLoading, onPinLocation }: BillBreakdownCardProps) {
  const grandTotal = withDelivery(totalAmount, delivery);
  const km = distanceLabel(delivery);
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
      {delivery?.needs_location ? (
        <Row label="Delivery charge" value="Pin location" valueColor={colors.error} onPress={onPinLocation} />
      ) : (
        <Row
          label={`Delivery Partner Fee${km ? ` (${km})` : ""}`}
          value={delivery?.fee ? formatMoney(delivery.fee, currency ?? "INR") : deliveryLoading ? "Calculating..." : "-"}
        />
      )}
      <View style={styles.divider} />
      <View style={styles.totalRow}>
        <Text variant="bodyMedium">Total Bill Amount</Text>
        <Text variant="h3">{formatMoney(grandTotal, currency ?? "INR")}</Text>
      </View>
      {savings > 0 ? (
        <Text variant="caption" color={colors.success} style={styles.savedNote}>
          Saved {formatMoney(savings, currency ?? "INR")} today
        </Text>
      ) : null}
    </View>
  );
}

function Row({ label, value, valueColor, onPress }: { label: string; value: string; valueColor?: string; onPress?: () => void }) {
  return (
    <Pressable style={styles.row} onPress={onPress} disabled={!onPress}>
      <Text variant="body" color={colors.textSecondary}>
        {label}
      </Text>
      <Text variant="bodyMedium" color={valueColor ?? colors.textPrimary}>
        {value}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    marginHorizontal: spacing.base,
    marginTop: spacing.xl,
    paddingTop: spacing.lg,
    borderTopWidth: 1,
    borderColor: colors.divider,
  },
  title: { marginBottom: spacing.md },
  row: { flexDirection: "row", justifyContent: "space-between", marginBottom: spacing.sm },
  divider: { height: 1, backgroundColor: colors.divider, marginVertical: spacing.sm },
  totalRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  savedNote: { marginTop: spacing.xs },
});
