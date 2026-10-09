import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Feather } from "@expo/vector-icons";
import { Text } from "../Text";
import { useCartItemCount } from "@/features/cart/useCart";
import { useBazaarStatus } from "@/features/bazaar/useBazaar";
import { useAuthStore } from "@/store/authStore";
import { colors, radius, spacing } from "@/theme";

/** Mirrors the backend defaults (FREE_DELIVERY_MIN_ITEMS / BAZAAR_PLUS_*);
 * the live values from /bazaar/status win whenever they are available. */
const DEFAULT_MIN_ITEMS = 15;
const DEFAULT_ORDERS_REQUIRED = 6;
const DEFAULT_WINDOW_DAYS = 7;

export interface BazaarSectionProps {
  onStartPress: () => void;
}

/**
 * "Bazaar" offer card: fill a basket with 15+ items for free delivery, and
 * place six such Bazaars in a week to become eligible for Gawacha Bazaar+.
 * Progress is real - cart units from the live cart, Bazaar orders from the
 * backend's rolling-window count (GET /bazaar/status).
 */
export function BazaarSection({ onStartPress }: BazaarSectionProps) {
  const signedIn = useAuthStore((s) => s.status === "authenticated");
  const cartItems = useCartItemCount();
  const { data: status } = useBazaarStatus();

  const minItems = status?.free_delivery_min_items ?? DEFAULT_MIN_ITEMS;
  const ordersRequired = status?.orders_required ?? DEFAULT_ORDERS_REQUIRED;
  const windowDays = status?.window_days ?? DEFAULT_WINDOW_DAYS;
  const bazaarOrders = Math.min(status?.bazaar_orders_in_window ?? 0, ordersRequired);
  const eligible = status?.eligible_for_bazaar_plus ?? false;

  const unlocked = cartItems >= minItems;
  const remaining = Math.max(0, minItems - cartItems);
  const progress = Math.min(1, cartItems / minItems);

  return (
    <View style={styles.outer}>
      <LinearGradient
        colors={["#0F3B2B", "#0A2A1F", "#061A12"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.card}
      >
        <View style={styles.glow} pointerEvents="none" />

        <Text variant="eyebrow" color={colors.accentLight}>
          THE BAZAAR OFFER
        </Text>
        <Text variant="displayL" color={colors.textInverse} style={styles.headline}>
          Fill your{" "}
          <Text variant="scriptLarge" color={colors.accentLight}>
            Bazaar.
          </Text>
        </Text>
        <Text variant="body" color="rgba(255,255,255,0.78)" style={styles.sub}>
          Pick {minItems} or more items in one basket and we deliver it free.
        </Text>

        {/* The hook: 15+ -> free delivery */}
        <View style={styles.hookRow}>
          <View style={styles.hookNumberWrap}>
            <Text variant="displayXL" color={colors.accent} style={styles.hookNumber}>
              {minItems}
              <Text variant="displayM" color={colors.accent}>
                +
              </Text>
            </Text>
            <Text variant="eyebrow" color="rgba(255,255,255,0.6)">
              ITEMS
            </Text>
          </View>
          <Feather name="arrow-right" size={22} color="rgba(255,255,255,0.45)" />
          <View style={styles.freePill}>
            <Feather name="truck" size={20} color={colors.primaryDark} />
            <View>
              <Text variant="bodyMedium" color={colors.primaryDark} style={styles.freeTitle}>
                FREE
              </Text>
              <Text variant="caption" color={colors.primaryDark}>
                delivery
              </Text>
            </View>
          </View>
        </View>

        {/* Live basket progress */}
        <View style={styles.progressBlock}>
          <View style={styles.progressTextRow}>
            <Text variant="bodySmall" color={colors.textInverse} style={styles.flex}>
              {unlocked
                ? "Your basket is a Bazaar - delivery is free"
                : cartItems === 0
                  ? "Your basket is empty - start your Bazaar"
                  : `${remaining} more ${remaining === 1 ? "item" : "items"} for free delivery`}
            </Text>
            <Text variant="bodySmall" color={colors.accentLight}>
              {Math.min(cartItems, minItems)}/{minItems}
            </Text>
          </View>
          <View style={styles.track}>
            <View style={[styles.fill, { width: `${progress * 100}%` }, unlocked && styles.fillDone]} />
          </View>
        </View>

        <View style={styles.divider} />

        {/* Gawacha Bazaar+ */}
        <View style={styles.plusHeader}>
          <View style={styles.plusBadge}>
            <Feather name="award" size={13} color={colors.primaryDark} />
            <Text variant="eyebrow" color={colors.primaryDark}>
              BAZAAR+
            </Text>
          </View>
          <Text variant="caption" color="rgba(255,255,255,0.6)">
            {bazaarOrders}/{ordersRequired} this week
          </Text>
        </View>
        <Text variant="bodyMedium" color={colors.textInverse} style={styles.plusTitle}>
          {eligible ? "You're eligible for Gawacha Bazaar+" : `Unlock Gawacha Bazaar+`}
        </Text>
        <Text variant="bodySmall" color="rgba(255,255,255,0.7)" style={styles.plusBody}>
          {eligible
            ? "Six Bazaars in a week - thank you for shopping the village way."
            : `Place ${ordersRequired} Bazaars (${minItems}+ items each) within ${windowDays} days to become eligible.`}
        </Text>

        <View style={styles.stampRow}>
          {Array.from({ length: ordersRequired }).map((_, i) => {
            const filled = i < bazaarOrders;
            return (
              <View key={i} style={[styles.stamp, filled && styles.stampFilled]}>
                {filled ? (
                  <Feather name="check" size={14} color={colors.primaryDark} />
                ) : (
                  <Text variant="caption" color="rgba(255,255,255,0.45)">
                    {i + 1}
                  </Text>
                )}
              </View>
            );
          })}
        </View>
        {!signedIn ? (
          <Text variant="caption" color="rgba(255,255,255,0.55)" style={styles.signInHint}>
            Sign in to track your Bazaars.
          </Text>
        ) : null}

        <Pressable
          onPress={onStartPress}
          style={({ pressed }) => [styles.cta, pressed && { opacity: 0.85 }]}
          accessibilityRole="button"
          accessibilityLabel="Start your Bazaar"
        >
          <Text variant="bodyMedium" color={colors.primaryDark} style={styles.ctaText}>
            {cartItems > 0 && !unlocked ? "Keep filling your Bazaar" : "Start your Bazaar"}
          </Text>
          <Feather name="arrow-right" size={18} color={colors.primaryDark} />
        </Pressable>
      </LinearGradient>
    </View>
  );
}

const styles = StyleSheet.create({
  outer: { paddingHorizontal: spacing.base, marginTop: spacing["3xl"] },
  card: { borderRadius: 28, padding: spacing.xl, overflow: "hidden" },
  glow: {
    position: "absolute",
    top: -70,
    right: -60,
    width: 220,
    height: 220,
    borderRadius: 110,
    backgroundColor: "rgba(217,165,42,0.16)",
  },
  headline: { marginTop: spacing.sm },
  sub: { marginTop: spacing.sm },
  hookRow: { flexDirection: "row", alignItems: "center", gap: spacing.lg, marginTop: spacing.xl },
  hookNumberWrap: { alignItems: "flex-start" },
  hookNumber: { lineHeight: 54 },
  freePill: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.accent,
    borderRadius: radius.pill,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  freeTitle: { fontWeight: "800", letterSpacing: 1 },
  progressBlock: { marginTop: spacing.xl },
  progressTextRow: { flexDirection: "row", alignItems: "flex-end", gap: spacing.sm },
  flex: { flex: 1 },
  track: {
    height: 8,
    borderRadius: radius.pill,
    backgroundColor: "rgba(255,255,255,0.14)",
    marginTop: spacing.sm,
    overflow: "hidden",
  },
  fill: { height: "100%", borderRadius: radius.pill, backgroundColor: colors.accent },
  fillDone: { backgroundColor: "#7FD6A0" },
  divider: { height: 1, backgroundColor: "rgba(255,255,255,0.14)", marginVertical: spacing.xl },
  plusHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  plusBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: colors.accentLight,
    borderRadius: radius.pill,
    paddingVertical: 4,
    paddingHorizontal: spacing.md,
  },
  plusTitle: { marginTop: spacing.md },
  plusBody: { marginTop: 4 },
  stampRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.lg },
  stamp: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1.5,
    borderStyle: "dashed",
    borderColor: "rgba(255,255,255,0.3)",
    alignItems: "center",
    justifyContent: "center",
  },
  stampFilled: { backgroundColor: colors.accent, borderStyle: "solid", borderColor: colors.accent },
  signInHint: { marginTop: spacing.sm },
  cta: {
    marginTop: spacing.xl,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    backgroundColor: colors.accentLight,
    borderRadius: radius.pill,
    paddingVertical: spacing.md + 2,
  },
  ctaText: { fontWeight: "700" },
});
