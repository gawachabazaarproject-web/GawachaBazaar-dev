import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { colors, spacing } from "@/theme";

export type Day = "today" | "tomorrow";
export type Slot = "morning" | "evening";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const SLOT_TIME: Record<Slot, string> = { morning: "6:30 AM – 9:00 AM", evening: "5:00 PM – 8:00 PM" };

/** "5 Oct" for today + `offsetDays`, from the device clock. */
function dayLabel(offsetDays: number): string {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  return `${date.getDate()} ${MONTHS[date.getMonth()]}`;
}

/** Short summary such as "Today, 6:30 AM – 9:00 AM" for the footer/summary. */
export function slotSummary(day: Day, slot: Slot): string {
  return `${day === "today" ? "Today" : "Tomorrow"}, ${SLOT_TIME[slot]}`;
}

/**
 * Delivery-slot picker. Real, interactive UI state (controlled by the
 * checkout screen so the footer/summary can echo it), but the backend has
 * no delivery-slot booking to persist it to, so nothing here is sent
 * anywhere.
 */
export function HarvestSlotSelector({
  day,
  slot,
  onDayChange,
  onSlotChange,
}: {
  day: Day;
  slot: Slot;
  onDayChange: (d: Day) => void;
  onSlotChange: (s: Slot) => void;
}) {
  return (
    <View>
      <View style={styles.dayRow}>
        <DayTab
          active={day === "today"}
          title={`Today, ${dayLabel(0)}`}
          sub="Fastest Express"
          onPress={() => onDayChange("today")}
        />
        <DayTab
          active={day === "tomorrow"}
          title={`Tomorrow, ${dayLabel(1)}`}
          sub="Dawn Harvest (4 AM)"
          onPress={() => onDayChange("tomorrow")}
        />
      </View>

      <SlotOption
        selected={slot === "morning"}
        onPress={() => onSlotChange("morning")}
        title="Morning Dawn Slot"
        time={SLOT_TIME.morning}
        description="Fresh A2 cow milk & Katol spinach, harvested at 4:30 AM."
        badge="Cold Chain"
        descIcon="leaf"
        art="leaf"
      />
      <SlotOption
        selected={slot === "evening"}
        onPress={() => onSlotChange("evening")}
        title="Evening Mandi Slot"
        time={SLOT_TIME.evening}
        description="Dispatched directly after village collection sorting."
        descIcon="truck"
        art="sun"
      />
    </View>
  );
}

function DayTab({ active, title, sub, onPress }: { active: boolean; title: string; sub: string; onPress: () => void }) {
  return (
    <Pressable style={[styles.dayCard, active && styles.dayCardActive]} onPress={onPress} accessibilityRole="button">
      <Text variant="bodyMedium" align="center" color={active ? colors.textInverse : colors.textPrimary}>
        {title}
      </Text>
      <Text variant="caption" align="center" color={active ? colors.primaryLight : colors.textSecondary}>
        {sub}
      </Text>
    </Pressable>
  );
}

function SlotOption({
  selected,
  onPress,
  title,
  time,
  description,
  badge,
  descIcon,
  art,
}: {
  selected: boolean;
  onPress: () => void;
  title: string;
  time: string;
  description: string;
  badge?: string;
  descIcon: "leaf" | "truck";
  art: "leaf" | "sun";
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
        <View style={styles.titleRow}>
          <Text variant="bodyMedium" style={styles.slotTitle}>
            {title}
          </Text>
          {badge ? (
            <View style={styles.coldChain}>
              <Text variant="label" color={colors.success}>
                {badge}
              </Text>
            </View>
          ) : null}
        </View>
        <Text variant="bodySmall" color={colors.textSecondary}>
          {time}
        </Text>
        <View style={styles.descRow}>
          {descIcon === "leaf" ? (
            <MaterialCommunityIcons name="leaf" size={16} color={colors.success} />
          ) : (
            <Feather name="truck" size={15} color={colors.textSecondary} />
          )}
          <Text variant="caption" color={colors.textSecondary} style={{ flex: 1 }}>
            {description}
          </Text>
        </View>
      </View>
      <View style={[styles.art, art === "sun" ? styles.artSun : styles.artLeaf]}>
        <MaterialCommunityIcons
          name={art === "sun" ? "white-balance-sunny" : "sprout"}
          size={30}
          color={art === "sun" ? "#E7A21B" : colors.success}
        />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  dayRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md },
  dayCard: {
    flex: 1,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.divider,
    backgroundColor: colors.surface,
    alignItems: "center",
  },
  dayCardActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  slot: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.divider,
    backgroundColor: colors.surface,
    marginBottom: spacing.sm,
  },
  slotActive: { borderColor: colors.primary, backgroundColor: colors.primaryLight },
  radio: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  radioActive: { borderColor: colors.primary, borderWidth: 2 },
  radioDot: { width: 12, height: 12, borderRadius: 6, backgroundColor: colors.primary },
  titleRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs, flexWrap: "wrap" },
  slotTitle: { fontWeight: "600" },
  coldChain: { backgroundColor: colors.successLight, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },
  descRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderColor: colors.divider,
  },
  art: { width: 54, height: 54, borderRadius: 27, alignItems: "center", justifyContent: "center" },
  artLeaf: { backgroundColor: "rgba(47,122,77,0.10)" },
  artSun: { backgroundColor: "rgba(231,162,27,0.14)" },
});
