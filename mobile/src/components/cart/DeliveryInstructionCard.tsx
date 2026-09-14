import React, { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { colors, radius, spacing } from "@/theme";

type Instruction = "no_contact" | "ring_bell";

const OPTIONS: { id: Instruction; icon: keyof typeof Feather.glyphMap; label: string; sub: string }[] = [
  { id: "no_contact", icon: "package", label: "No-contact", sub: "Drop at door" },
  { id: "ring_bell", icon: "bell", label: "Ring bell", sub: "& leave safely" },
];

/**
 * Delivery-instruction preference. This is real, interactive UI state
 * (the selection genuinely changes and is visible) but there's no
 * backend field to persist it to yet - structured so it's a one-line
 * change to wire up once one exists, per the "mock data replaceable by
 * API data" allowance.
 */
export function DeliveryInstructionCard() {
  const [selected, setSelected] = useState<Instruction>("no_contact");
  return (
    <View style={styles.card}>
      <Text variant="h3" style={styles.title}>
        Delivery Instructions
      </Text>
      <View style={styles.row}>
        {OPTIONS.map((opt) => {
          const active = selected === opt.id;
          return (
            <Pressable
              key={opt.id}
              style={[styles.option, active && styles.optionActive]}
              onPress={() => setSelected(opt.id)}
              accessibilityRole="radio"
              accessibilityState={{ selected: active }}
            >
              <Feather name={opt.icon} size={16} color={active ? colors.primary : colors.textSecondary} />
              <View>
                <Text variant="bodySmall" color={active ? colors.primary : colors.textPrimary}>
                  {opt.label}
                </Text>
                <Text variant="caption" color={colors.textSecondary}>
                  {opt.sub}
                </Text>
              </View>
            </Pressable>
          );
        })}
      </View>
    </View>
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
  row: { flexDirection: "row", gap: spacing.sm },
  option: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.none,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  optionActive: { borderColor: colors.primary, backgroundColor: colors.primaryLight },
});
