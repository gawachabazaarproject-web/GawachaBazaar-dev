import React from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "../Text";
import { EditorialLink } from "../EditorialLink";
import { colors, spacing } from "@/theme";

export interface SectionHeadingProps {
  /** Chapter-numbering micro-label, e.g. "03 / 09". Used sparingly, only
   * on the home screen's major sections - part of the brand's visual
   * identity carried over from the website. */
  index?: string;
  eyebrow: string;
  title: string;
  /** A single word/phrase rendered in the Instrument Serif italic accent,
   * appended after `title` (mirrors the website's headline pattern). */
  scriptSuffix?: string;
  description?: string;
  onSeeAll?: () => void;
  seeAllLabel?: string;
}

/** Shared section header for every home-screen carousel/block - editorial
 * label, serif heading (with an optional italic accent word), optional
 * description, and a "View all →" link. Keeps every section's typography
 * hierarchy consistent instead of each section inventing its own. */
export function SectionHeading({
  index,
  eyebrow,
  title,
  scriptSuffix,
  description,
  onSeeAll,
  seeAllLabel = "View all",
}: SectionHeadingProps) {
  return (
    <View style={styles.wrap}>
      <View style={styles.labelRow}>
        <Text variant="eyebrow" color={colors.accentDark}>
          {eyebrow}
        </Text>
        {index ? (
          <Text variant="eyebrow" color={colors.textMuted}>
            {index}
          </Text>
        ) : null}
      </View>
      <Text variant="h1" style={styles.title}>
        {title}
        {scriptSuffix ? (
          <Text variant="script" color={colors.primary}>
            {" "}
            {scriptSuffix}
          </Text>
        ) : null}
      </Text>
      {description ? (
        <Text variant="body" color={colors.textSecondary} style={styles.description}>
          {description}
        </Text>
      ) : null}
      {onSeeAll ? (
        <EditorialLink onPress={onSeeAll} style={styles.link}>
          {seeAllLabel}
        </EditorialLink>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: spacing.base, marginBottom: spacing.base },
  labelRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  title: { marginTop: spacing.xs },
  description: { marginTop: spacing.sm, maxWidth: "88%" },
  link: { marginTop: spacing.base },
});
