import React from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "./Text";
import { formatMoney } from "@/utils/money";
import { colors, spacing } from "@/theme";

export interface PriceTagProps {
  amount: string;
  currency?: string;
  mrp?: string | null;
  size?: "md" | "lg";
}

/** MRP is shown struck-through only when it's genuinely higher than the
 * selling price - the backend does not currently send an MRP field
 * (Phase 19 limitation), so this stays ready to light up once it does. */
export function PriceTag({ amount, currency = "INR", mrp, size = "md" }: PriceTagProps) {
  const showMrp = mrp && Number.parseFloat(mrp) > Number.parseFloat(amount);
  return (
    <View style={styles.row}>
      <Text variant={size === "lg" ? "priceLarge" : "price"} color={colors.price}>
        {formatMoney(amount, currency)}
      </Text>
      {showMrp ? (
        <Text variant="bodySmall" color={colors.strikethrough} style={styles.mrp}>
          {formatMoney(mrp!, currency)}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "baseline", gap: spacing.xs },
  mrp: { textDecorationLine: "line-through" },
});
