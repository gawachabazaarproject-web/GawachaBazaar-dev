import React from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "@/components/Text";
import { colors } from "@/theme";

const STEPS = ["Address", "Delivery", "Payment"];

/** Three-step progress indicator shown under the checkout header. */
export function CheckoutStepper({ active = 1 }: { active?: 1 | 2 | 3 }) {
  return (
    <View style={styles.row}>
      {STEPS.map((label, i) => {
        const step = i + 1;
        const isActive = step === active;
        const done = step < active;
        return (
          <React.Fragment key={label}>
            {i > 0 ? <View style={styles.line} /> : null}
            <View style={styles.step}>
              <View style={[styles.circle, (isActive || done) && styles.circleActive]}>
                <Text variant="bodySmall" color={isActive || done ? colors.textInverse : colors.textSecondary} style={styles.num}>
                  {step}
                </Text>
              </View>
              <Text variant="caption" color={isActive ? colors.textPrimary : colors.textSecondary} style={isActive && styles.activeLabel}>
                {label}
              </Text>
            </View>
          </React.Fragment>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "flex-start", paddingHorizontal: 24, paddingTop: 4, paddingBottom: 14 },
  step: { alignItems: "center", gap: 5, width: 60 },
  line: { flex: 1, height: 1, backgroundColor: colors.border, marginTop: 13 },
  circle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  circleActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  num: { fontWeight: "600" },
  activeLabel: { fontWeight: "600" },
});
