import React, { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { colors, radius, spacing } from "@/theme";

type Day = "today" | "tomorrow";
type Slot = "morning" | "evening";

/**
 * Delivery-slot picker. This is real, interactive UI state - selecting a
 * day/slot genuinely changes and is reflected on screen - but there is
 * no delivery-slot-booking system in the backend to persist it to, so
 * nothing here is sent anywhere. Structured as a self-contained
 * component so it's a one-line swap for a real API-backed selector once
 * that feature exists, per the "mock data replaceable by API data"
 * allowance - not a fake button, since it doesn't claim to submit
 * anything.
 */
export function HarvestSlotSelector() {
  const [day, setDay] = useState<Day>("today");
  const [slot, setSlot] = useState<Slot>("morning");

  return (
    <View>
      <View style={styles.dayRow}>
        <Pressable style={[styles.dayCard, day === "today" && styles.dayCardActive]} onPress={() => setDay("today")}>
          <Text variant="bodyMedium" color={day === "today" ? colors.textInverse : colors.textPrimary}>
            Today, 24 Oct
          </Text>
          <Text variant="caption" color={day === "today" ? colors.primaryLight : colors.textSecondary}>
            Fastest Express
          </Text>
        </Pressable>
        <Pressable style={[styles.dayCard, day === "tomorrow" && styles.dayCardActive]} onPress={() => setDay("tomorrow")}>
          <Text variant="bodyMedium" color={day === "tomorrow" ? colors.textInverse : colors.textPrimary}>
            Tomorrow, 25 Oct
          </Text>
          <Text variant="caption" color={day === "tomorrow" ? colors.primaryLight : colors.textSecondary}>
            Dawn Harvest (4 AM)
          </Text>
        </Pressable>
      </View>

      <SlotOption
        selected={slot === "morning"}
        onPress={() => setSlot("morning")}
        title="Morning Dawn Slot"
        time="6:30 AM - 9:00 AM"
        description="Fresh A2 cow milk & Katol spinach, harvested at 4:30 AM."
        badge="Cold Chain"
      />
      <SlotOption
        selected={slot === "evening"}
        onPress={() => setSlot("evening")}
        title="Evening Mandi Slot"
        time="5:00 PM - 8:00 PM"
        description="Dispatched directly after village collection sorting."
      />
    </View>
  );
}

function SlotOption({
  selected,
  onPress,
  title,
  time,
  description,
  badge,
}: {
  selected: boolean;
  onPress: () => void;
  title: string;
  time: string;
  description: string;
  badge?: string;
}) {
  return (
    <Pressable
      style={[styles.slot, selected && styles.slotActive]}
      onPress={onPress}
      accessibilityRole="radio"
      accessibilityState={{ selected }}
    >
      <View style={[styles.radio, selected && styles.radioActive]}>{selected ? <View style={styles.radioDot} /> : null}</View>
      <View style={{ flex: 1 }}>
        <View style={styles.slotTitleRow}>
          <Text variant="bodyMedium">{title}</Text>
          {badge ? (
            <View style={styles.coldChainBadge}>
              <Text variant="label" color={colors.success}>
                {badge}
              </Text>
            </View>
          ) : null}
          <Text variant="caption" color={colors.textSecondary}>
            {time}
          </Text>
        </View>
        <View style={styles.slotDescRow}>
          <Feather name={badge ? "droplet" : "truck"} size={11} color={colors.textSecondary} />
          <Text variant="caption" color={colors.textSecondary} style={{ flex: 1 }}>
            {description}
          </Text>
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  dayRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md },
  dayCard: {
    flex: 1,
    padding: spacing.sm,
    borderRadius: radius.none,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  dayCardActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  slot: {
    flexDirection: "row",
    gap: spacing.sm,
    padding: spacing.sm,
    borderRadius: radius.none,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.sm,
  },
  slotActive: { borderColor: colors.primary, backgroundColor: colors.primaryLight },
  radio: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
  },
  radioActive: { borderColor: colors.primary },
  radioDot: { width: 9, height: 9, borderRadius: 5, backgroundColor: colors.primary },
  slotTitleRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs, flexWrap: "wrap" },
  coldChainBadge: { backgroundColor: colors.successLight, borderRadius: radius.none, paddingHorizontal: 4, paddingVertical: 1 },
  slotDescRow: { flexDirection: "row", alignItems: "flex-start", gap: 4, marginTop: 2 },
});
