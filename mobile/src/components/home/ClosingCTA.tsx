import React from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "../Text";
import { EditorialLink } from "../EditorialLink";
import { colors, spacing } from "@/theme";

export interface ClosingCTAProps {
  onPress: () => void;
}

/** Closing brand statement, dark full-width panel - mirrors the
 * website's closing tagline ("From Our Village to Your Table"). */
export function ClosingCTA({ onPress }: ClosingCTAProps) {
  return (
    <View style={styles.wrap}>
      <Text variant="eyebrow" color={colors.accentLight}>
        GAWACHA BAZAAR
      </Text>
      <Text variant="displayM" color={colors.textInverse} style={styles.headline}>
        From our village{"\n"}to{" "}
        <Text variant="script" color={colors.accentLight}>
          your table.
        </Text>
      </Text>
      <EditorialLink tone="light" onPress={onPress} style={styles.link}>
        Start shopping
      </EditorialLink>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { backgroundColor: colors.primary, paddingHorizontal: spacing.base, paddingVertical: spacing["4xl"] },
  headline: { marginTop: spacing.sm },
  link: { marginTop: spacing["2xl"] },
});
