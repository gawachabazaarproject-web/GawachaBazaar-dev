import React from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "@/components/Text";
import { colors, radius, spacing } from "@/theme";

export interface CheckoutSectionProps {
  number: number;
  /** Short editorial label for the "0N / LABEL" chapter-style heading,
   * e.g. "ADDRESS", "DELIVERY", "PAYMENT", "ORDER SUMMARY". */
  label: string;
  title: string;
  badge?: string;
  children: React.ReactNode;
}

/** Numbered checkout section - editorial "0N / LABEL" heading matching
 * the website/home section-numbering language, in place of a decorative
 * numbered circle. Checkout stays plain and predictable by design: no
 * card chrome, just a divider between sections. */
export function CheckoutSection({ number, label, title, badge, children }: CheckoutSectionProps) {
  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <Text variant="eyebrow" color={colors.accentDark}>
          {String(number).padStart(2, "0")} / {label.toUpperCase()}
        </Text>
        {badge ? (
          <View style={styles.pill}>
            <Text variant="label" color={colors.accentDark}>
              {badge}
            </Text>
          </View>
        ) : null}
      </View>
      <Text variant="h3" style={styles.title}>
        {title}
      </Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingTop: spacing.xl,
    marginBottom: spacing.xl,
    borderTopWidth: 1,
    borderColor: colors.divider,
  },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  title: { marginTop: spacing.xs, marginBottom: spacing.md },
  pill: { backgroundColor: colors.accentLight, borderRadius: radius.none, paddingHorizontal: spacing.xs, paddingVertical: 3 },
});
