import React from "react";
import { Alert, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { useAuthStore } from "@/store/authStore";
import { colors, spacing } from "@/theme";

interface MenuItem {
  icon: keyof typeof Feather.glyphMap;
  label: string;
  onPress: () => void;
  destructive?: boolean;
}

export default function AccountScreen() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

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
        { icon: "package", label: "Orders", onPress: () => router.push("/(tabs)/orders") },
        { icon: "briefcase", label: "Bulk requests", onPress: () => router.push("/bulk/requests") },
      ],
    },
    {
      label: "SUPPORT",
      items: [
        { icon: "help-circle", label: "Support", onPress: () => router.push("/account/support") },
        { icon: "settings", label: "Settings", onPress: () => router.push("/account/settings") },
      ],
    },
    {
      label: "",
      items: [{ icon: "log-out", label: "Log out", onPress: handleLogout, destructive: true }],
    },
  ];

  return (
    <Screen edges={["top"]}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        <View style={styles.heroText}>
          <Text variant="eyebrow" color={colors.accentDark}>
            MY GAWACHA BAZAAR
          </Text>
          <Text variant="displayM" style={{ marginTop: spacing.xs }}>
            Account
          </Text>
        </View>

        <View style={styles.header}>
          <View style={styles.avatar}>
            <Text variant="displayM" color={colors.primary}>
              {user?.name?.charAt(0).toUpperCase() ?? "?"}
            </Text>
          </View>
          <View style={{ marginLeft: spacing.base, flex: 1 }}>
            <Text variant="h3" numberOfLines={1}>
              {user?.name ?? "Guest"}
            </Text>
            <Text variant="bodySmall" color={colors.textSecondary} numberOfLines={1}>
              {user?.email}
            </Text>
          </View>
        </View>

        {sections.map((section, sIdx) => (
          <View key={sIdx} style={styles.section}>
            {section.label ? (
              <Text variant="eyebrow" color={colors.textMuted} style={styles.sectionLabel}>
                {section.label}
              </Text>
            ) : null}
            {section.items.map((item, iIdx) => (
              <Pressable
                key={item.label}
                style={[styles.row, iIdx === section.items.length - 1 && styles.rowLast]}
                onPress={item.onPress}
              >
                <Feather name={item.icon} size={18} color={item.destructive ? colors.error : colors.textSecondary} />
                <Text variant="bodyLarge" color={item.destructive ? colors.error : colors.textPrimary} style={styles.rowLabel}>
                  {item.label}
                </Text>
                {!item.destructive ? <Feather name="arrow-up-right" size={16} color={colors.textMuted} /> : null}
              </Pressable>
            ))}
          </View>
        ))}

        <Text variant="caption" color={colors.textMuted} align="center" style={styles.version}>
          GawachaBazaar v1.0.0
        </Text>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingBottom: spacing.xl },
  heroText: { paddingHorizontal: spacing.base, marginTop: spacing.lg },
  header: { flexDirection: "row", alignItems: "center", paddingHorizontal: spacing.base, marginTop: spacing.xl, paddingBottom: spacing.xl, borderBottomWidth: 1, borderColor: colors.divider },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  section: { marginTop: spacing.xl, paddingHorizontal: spacing.base },
  sectionLabel: { marginBottom: spacing.sm },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  rowLast: { borderBottomWidth: 0 },
  rowLabel: { flex: 1, marginLeft: spacing.md },
  version: { marginTop: spacing["2xl"], marginBottom: spacing.xl },
});
