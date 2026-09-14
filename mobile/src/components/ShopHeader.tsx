import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { Feather } from "@expo/vector-icons";
import { Text } from "./Text";
import { colors, fontFamily, radius, spacing } from "@/theme";

const LOGO_ASPECT_RATIO = 1369 / 1149;
const LOGO_HEIGHT = 40;

export interface ShopHeaderProps {
  locationLabel: string;
  onLocationPress: () => void;
  onAccountPress: () => void;
  onCartPress?: () => void;
  /** Compact by default; Home's version keeps a hair more breathing room. */
  compact?: boolean;
}

/**
 * Shared header for every shopping screen (Home, Search, Cart,
 * Categories) - one brand/navigation language across the app. Logo +
 * full delivery address (the address IS the primary content, given the
 * width it needs) + cart/account shortcuts. Row 2: illustrative ETA badge
 * (explicitly authorized, no real logistics system behind it) + the
 * Marathi brand line.
 */
export function ShopHeader({
  locationLabel,
  onLocationPress,
  onAccountPress,
  onCartPress,
  compact = true,
}: ShopHeaderProps) {
  return (
    <View style={[styles.wrap, { paddingTop: compact ? spacing.md : spacing.lg }]}>
      <View style={styles.row}>
        <Image
          source={require("../../assets/logo.jpeg")}
          style={{ height: LOGO_HEIGHT, width: LOGO_HEIGHT * LOGO_ASPECT_RATIO, borderRadius: 10 }}
          contentFit="cover"
        />
        <Pressable style={styles.locationCol} onPress={onLocationPress} hitSlop={4}>
          <View style={styles.locationLabelRow}>
            <Feather name="map-pin" size={11} color={colors.accentDark} />
            <Text variant="label" color={colors.accentDark}>
              DELIVERING TO
            </Text>
          </View>
          <View style={styles.locationRow}>
            <Text variant="bodyMedium" numberOfLines={2} style={{ flex: 1 }}>
              {locationLabel}
            </Text>
            <Feather name="chevron-down" size={16} color={colors.textSecondary} />
          </View>
        </Pressable>
        {onCartPress ? (
          <Pressable style={styles.iconButton} onPress={onCartPress} accessibilityRole="button" accessibilityLabel="Cart">
            <Feather name="shopping-bag" size={18} color={colors.textPrimary} />
          </Pressable>
        ) : null}
        <Pressable style={styles.iconButton} onPress={onAccountPress} accessibilityRole="button" accessibilityLabel="Account">
          <Feather name="user" size={18} color={colors.textPrimary} />
        </Pressable>
      </View>
      <View style={styles.subRow}>
        <View style={styles.etaBadge}>
          <Feather name="zap" size={11} color={colors.textOnAccent} />
          <Text variant="label" color={colors.textOnAccent}>
            25 MINS
          </Text>
        </View>
        <Text variant="caption" color={colors.textMuted} style={{ fontFamily: fontFamily.devanagari }}>
          गावचा बाजार
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: spacing.base, paddingBottom: spacing.sm },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  locationCol: { flex: 1, gap: 3 },
  locationLabelRow: { flexDirection: "row", alignItems: "center", gap: 4 },
  locationRow: { flexDirection: "row", alignItems: "center", gap: 4 },
  iconButton: {
    width: 40,
    height: 40,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.divider,
    alignItems: "center",
    justifyContent: "center",
  },
  subRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.md },
  etaBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    backgroundColor: colors.accent,
    borderRadius: radius.none,
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
  },
});
