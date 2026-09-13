import React from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "@/components/Text";
import { colors, radius, shadows, spacing } from "@/theme";

export interface CheckoutSectionProps {
  number: number;
  title: string;
  badge?: string;
  children: React.ReactNode;
}

/** Numbered checkout section card - shared shell for Delivery Address,
 * Farm Harvest Slot, and Payment Options, matching the reference's
 * numbered-circle section language. */
export function CheckoutSection({ number, title, badge, children }: CheckoutSectionProps) {
  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <View style={styles.numberBadge}>
          <Text variant="captionMedium" color={colors.textInverse}>
            {number}
          </Text>
        </View>
        <Text variant="h3" style={{ flex: 1 }}>
          {title}
        </Text>
        {badge ? (
          <View style={styles.pill}>
            <Text variant="label" color={colors.accentDark}>
              {badge}
            </Text>
          </View>
        ) : null}
      </View>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.divider,
    padding: spacing.base,
    marginBottom: spacing.base,
    ...shadows.card,
  },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.md },
  numberBadge: {
    width: 22,
    height: 22,
    borderRadius: radius.pill,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  pill: { backgroundColor: colors.accentLight, borderRadius: radius.xs, paddingHorizontal: spacing.xs, paddingVertical: 3 },
});
