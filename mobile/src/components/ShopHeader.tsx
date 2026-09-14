import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { Feather } from "@expo/vector-icons";
import { Text } from "./Text";
import { colors, radius, spacing } from "@/theme";

const LOGO_ASPECT_RATIO = 1369 / 1149;
const LOGO_HEIGHT = 26;

export interface ShopHeaderProps {
  locationLabel: string;
  onLocationPress: () => void;
  onAccountPress: () => void;
  /** Compact by default; Home's version keeps a hair more breathing room. */
  compact?: boolean;
}

/**
 * Shared compact header for every shopping screen (Home, Search, Cart,
 * Checkout) - one brand/navigation language across the app, per the
 * design system. Row 1: logo + delivery location + notification/account.
 * Row 2: illustrative ETA badge (explicitly authorized, no real
 * logistics system behind it) + the Marathi brand line.
 */
export function ShopHeader({ locationLabel, onLocationPress, onAccountPress, compact = true }: ShopHeaderProps) {
  return (
    <View style={[styles.wrap, { paddingTop: compact ? spacing.sm : spacing.md }]}>
      <View style={styles.row}>
        <Image
          source={require("../../assets/logo.jpeg")}
          style={{ height: LOGO_HEIGHT, width: LOGO_HEIGHT * LOGO_ASPECT_RATIO, borderRadius: radius.xs }}
          contentFit="cover"
        />
        <Pressable style={styles.locationCol} onPress={onLocationPress}>
          <View style={styles.locationRow}>
            <Feather name="map-pin" size={12} color={colors.primary} />
            <Text variant="bodyMedium" numberOfLines={1} style={{ flex: 1 }}>
              {locationLabel}
            </Text>
            <Feather name="chevron-down" size={14} color={colors.textSecondary} />
          </View>
        </Pressable>
        <View style={styles.iconButton}>
          <Feather name="bell" size={18} color={colors.textPrimary} />
        </View>
        <Pressable style={styles.avatarButton} onPress={onAccountPress} accessibilityRole="button" accessibilityLabel="Account">
          <Feather name="user" size={15} color={colors.textInverse} />
        </Pressable>
      </View>
      <View style={styles.subRow}>
        <View style={styles.etaBadge}>
          <Feather name="zap" size={11} color={colors.textOnAccent} />
          <Text variant="label" color={colors.textOnAccent}>
            25 MINS
          </Text>
        </View>
        <Text variant="caption" color={colors.textMuted}>
          गावचा बाजार
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: spacing.base, paddingBottom: spacing.xs },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  locationCol: { flex: 1 },
  locationRow: { flexDirection: "row", alignItems: "center", gap: 4 },
  iconButton: { width: 30, height: 30, alignItems: "center", justifyContent: "center" },
  avatarButton: {
    width: 30,
    height: 30,
    borderRadius: radius.pill,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  subRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: 4 },
  etaBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    backgroundColor: colors.accent,
    borderRadius: radius.xs,
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
  },
});
