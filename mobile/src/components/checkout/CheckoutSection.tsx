import React from "react";
import { StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { colors, spacing } from "@/theme";

export interface CheckoutSectionProps {
  number: number;
  /** Short label for the heading, e.g. "ADDRESS", "PAYMENT". */
  label: string;
  /** Serif title under the heading. Omit for the compact "01  LABEL" style. */
  title?: string;
  badge?: string;
  badgeIcon?: keyof typeof Feather.glyphMap;
  /** Right-aligned element in the heading row (e.g. a "Change" link). */
  action?: React.ReactNode;
  children: React.ReactNode;
}

/** Numbered checkout section. With a `title` it renders the editorial
 * "0N / LABEL" eyebrow plus serif title; without one, the compact
 * "01   LABEL" row used for the address and delivery sections. */
export function CheckoutSection({ number, label, title, badge, badgeIcon, action, children }: CheckoutSectionProps) {
  const num = String(number).padStart(2, "0");
  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        {title ? (
          <Text variant="eyebrow" color={colors.accentDark}>
            {num} / {label.toUpperCase()}
          </Text>
        ) : (
          <View style={styles.compactLabel}>
            <Text variant="h3" color={colors.accentDark} style={styles.compactNumber}>
              {num}
            </Text>
            <Text variant="eyebrow" color={colors.textSecondary}>
              {label.toUpperCase()}
            </Text>
          </View>
        )}
        {badge ? (
          <View style={styles.pill}>
            {badgeIcon ? <Feather name={badgeIcon} size={12} color={colors.accentDark} /> : null}
            <Text variant="label" color={colors.textPrimary}>
              {badge}
            </Text>
          </View>
        ) : (
          action ?? null
        )}
      </View>
      {title ? (
        <Text variant="h2" color={colors.primary} style={styles.title}>
          {title}
        </Text>
      ) : null}
      <View style={title ? undefined : styles.bodyGap}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingTop: spacing.lg,
    marginBottom: spacing.lg,
    borderTopWidth: 1,
    borderColor: colors.divider,
  },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  compactLabel: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  compactNumber: { letterSpacing: 1 },
  title: { marginTop: spacing.xs, marginBottom: spacing.md },
  bodyGap: { marginTop: spacing.md },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: colors.accentLight,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
});
