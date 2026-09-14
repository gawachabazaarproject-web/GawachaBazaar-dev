import React from "react";
import { Pressable, StyleSheet } from "react-native";
import { Text } from "./Text";
import { colors, radius, spacing } from "@/theme";

export interface FilterChipProps {
  label: string;
  selected: boolean;
  onPress: () => void;
}

/** Compact selectable chip (32px, per the design system's Filter Pills
 * spec) - used for quick related-search terms and category filters. */
export function FilterChip({ label, selected, onPress }: FilterChipProps) {
  return (
    <Pressable style={[styles.chip, selected && styles.chipSelected]} onPress={onPress}>
      <Text variant="bodySmall" color={selected ? colors.background : colors.textPrimary}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    height: 32,
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    borderRadius: radius.none,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.borderStrong,
  },
  chipSelected: { backgroundColor: colors.primary, borderColor: colors.primary },
});
