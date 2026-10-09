import React from "react";
import { Alert, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { CART_BAR_CLEARANCE } from "@/components/CartBar";
import { useAuthStore } from "@/store/authStore";
import { useWishlist } from "@/features/wishlist/useWishlist";
import { colors, fontFamily, spacing } from "@/theme";

interface MenuItem {
  icon: keyof typeof Feather.glyphMap;
  label: string;
  onPress: () => void;
  /** Count bubble before the chevron; hidden when 0. */
  badge?: number;
}

export default function AccountScreen() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const { data: wishlist } = useWishlist();
  const wishlistCount = wishlist?.product_ids.length ?? 0;

  const handleLogout = () => {
    Alert.alert("Log out", "Are you sure you want to log out?", [
      { text: "Cancel", style: "cancel" },
      { text: "Log out", style: "destructive", onPress: () => logout() },
    ]);
  };

  const sections: { label: string; items: MenuItem[] }[] = [
    {
      label: "SHOPPING",
      items: [
        { icon: "user", label: "Profile", onPress: () => router.push("/account/profile") },
        { icon: "map-pin", label: "Saved addresses", onPress: () => router.push("/address") },
        { icon: "heart", label: "Wishlist", badge: wishlistCount, onPress: () => router.push("/wishlist" as never) },
        { icon: "package", label: "Orders", onPress: () => router.push("/(tabs)/orders") },
        { icon: "shopping-bag", label: "Bulk requests", onPress: () => router.push("/bulk/requests") },
      ],
    },
    {
      label: "SUPPORT",
      items: [
        { icon: "help-circle", label: "Support", onPress: () => router.push("/account/support") },
        { icon: "settings", label: "Settings", onPress: () => router.push("/account/settings") },
      ],
    },
  ];

  const initial = user?.name?.trim().charAt(0).toUpperCase() || "?";

  return (
    <Screen edges={["top"]}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingBottom: CART_BAR_CLEARANCE }}
      >
        {/* Header */}
        <View style={styles.header}>
          <Image
            source={require("../../assets/account-hero-art.png")}
            style={styles.headerArt}
            contentFit="contain"
          />
          <Text variant="eyebrow" color={colors.accentDark}>
            MY GAWACHA BAZAAR
          </Text>
          <Text variant="displayM" color={colors.primary} style={styles.title}>
            Account
          </Text>
          <Text variant="bodySmall" color={colors.textSecondary} style={styles.subtitle}>
            Manage your profile, orders and preferences
          </Text>
          <Pressable
            onPress={() => router.push("/account/settings")}
            style={styles.gear}
            accessibilityRole="button"
            accessibilityLabel="Settings"
          >
            <Feather name="settings" size={20} color={colors.primary} />
          </Pressable>
        </View>

        {/* Profile card */}
        <Pressable
          style={styles.profileCard}
          onPress={() => router.push("/account/profile")}
          accessibilityRole="button"
          accessibilityLabel="Open profile"
        >
          <Feather name="feather" size={120} color="rgba(255,255,255,0.05)" style={styles.leafA} />
          <Feather name="feather" size={70} color="rgba(255,255,255,0.05)" style={styles.leafB} />
          <View style={styles.avatar}>
            <Text variant="displayM" color={colors.primary} style={styles.avatarLetter}>
              {initial}
            </Text>
          </View>
          <View style={styles.profileText}>
            <Text variant="eyebrow" color={colors.accent}>
              YOUR ACCOUNT
            </Text>
            <Text variant="displayM" color={colors.textInverse} numberOfLines={1} style={styles.name}>
              {user?.name ?? "Guest"}
            </Text>
            <Text variant="bodySmall" color="rgba(255,255,255,0.85)" numberOfLines={1} style={styles.email}>
              {user?.email}
            </Text>
          </View>
          <View style={styles.profileChevron}>
            <Feather name="chevron-right" size={18} color={colors.textInverse} />
          </View>
        </Pressable>

        {/* Menu sections */}
        {sections.map((section) => (
          <View key={section.label}>
            <Text variant="eyebrow" color={colors.textSecondary} style={styles.sectionLabel}>
              {section.label}
            </Text>
            <View style={styles.card}>
              {section.items.map((item, i) => (
                <Pressable
                  key={item.label}
                  style={[styles.row, i < section.items.length - 1 && styles.rowDivider]}
                  onPress={item.onPress}
                  accessibilityRole="button"
                >
                  <View style={styles.tile}>
                    <Feather name={item.icon} size={20} color={colors.primary} />
                  </View>
                  <Text variant="bodyLarge" color={colors.textPrimary} style={styles.rowLabel}>
                    {item.label}
                  </Text>
                  {item.badge ? (
                    <View style={styles.badge}>
                      <Text variant="captionMedium" color={colors.textInverse}>
                        {item.badge > 99 ? "99+" : item.badge}
                      </Text>
                    </View>
                  ) : null}
                  <Feather name="chevron-right" size={18} color={colors.textPrimary} />
                </Pressable>
              ))}
            </View>
          </View>
        ))}

        {/* Log out */}
        <Pressable style={styles.logout} onPress={handleLogout} accessibilityRole="button">
          <Feather name="log-out" size={22} color={colors.error} />
          <Text variant="bodyLarge" color={colors.error} style={styles.rowLabel}>
            Log out
          </Text>
          <Feather name="chevron-right" size={18} color={colors.textSecondary} />
        </Pressable>

        <Text variant="caption" color={colors.textMuted} align="center" style={styles.version}>
          GawachaBazaar v1.0.0
        </Text>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: spacing.base, paddingTop: spacing.lg, paddingBottom: spacing.base, minHeight: 132 },
  headerArt: { position: "absolute", top: 0, right: 0, width: 159, height: 124 },
  title: { fontFamily: fontFamily.headlineBold, fontSize: 36, lineHeight: 44, marginTop: 2 },
  subtitle: { marginTop: 2, fontSize: 12.5 },
  gear: {
    position: "absolute",
    top: 25,
    right: 15,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "rgba(255,255,255,0.85)",
    alignItems: "center",
    justifyContent: "center",
  },

  profileCard: {
    marginHorizontal: spacing.base,
    marginTop: spacing.sm,
    borderRadius: 20,
    backgroundColor: colors.primaryDark,
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.base,
    paddingHorizontal: spacing.base,
    gap: spacing.base,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOpacity: 0.18,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 5 },
    elevation: 5,
  },
  leafA: { position: "absolute", right: 30, top: -18, transform: [{ rotate: "20deg" }] },
  leafB: { position: "absolute", right: 70, bottom: -14, transform: [{ rotate: "-30deg" }] },
  avatar: {
    width: 68,
    height: 68,
    borderRadius: 34,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarLetter: { fontFamily: fontFamily.headlineBold, fontSize: 30, lineHeight: 36 },
  profileText: { flex: 1, minWidth: 0 },
  name: { fontFamily: fontFamily.headlineBold, fontSize: 19, lineHeight: 25, marginTop: 2 },
  email: { fontSize: 12.5, marginTop: 2 },
  profileChevron: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: "rgba(255,255,255,0.14)",
    alignItems: "center",
    justifyContent: "center",
  },

  sectionLabel: { marginTop: spacing.xl, marginBottom: spacing.sm, paddingHorizontal: spacing.lg, letterSpacing: 3 },
  card: {
    marginHorizontal: spacing.base,
    backgroundColor: colors.surface,
    borderRadius: 18,
    paddingHorizontal: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingVertical: spacing.sm + 2 },
  rowDivider: { borderBottomWidth: 1, borderBottomColor: colors.divider },
  tile: {
    width: 38,
    height: 38,
    borderRadius: 11,
    backgroundColor: colors.successLight,
    alignItems: "center",
    justifyContent: "center",
  },
  rowLabel: { flex: 1, fontFamily: fontFamily.medium, fontSize: 15 },
  badge: {
    minWidth: 22,
    height: 22,
    paddingHorizontal: 6,
    borderRadius: 11,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },

  logout: {
    marginHorizontal: spacing.base,
    marginTop: spacing.base,
    backgroundColor: colors.dangerTint,
    borderRadius: 18,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.base,
    paddingHorizontal: spacing.base,
  },
  version: { marginTop: spacing.md },
});
