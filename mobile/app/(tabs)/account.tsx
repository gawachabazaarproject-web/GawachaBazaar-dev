import React from "react";
import { Alert, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { useAuthStore } from "@/store/authStore";
import { colors, radius, spacing } from "@/theme";

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

  const sections: { title?: string; items: MenuItem[] }[] = [
    {
      items: [
        { icon: "user", label: "Profile", onPress: () => router.push("/account/profile") },
        { icon: "map-pin", label: "Saved addresses", onPress: () => router.push("/address") },
        { icon: "package", label: "Orders", onPress: () => router.push("/(tabs)/orders") },
      ],
    },
    {
      items: [
        { icon: "help-circle", label: "Support", onPress: () => router.push("/account/support") },
        { icon: "settings", label: "Settings", onPress: () => router.push("/account/settings") },
      ],
    },
    {
      items: [{ icon: "log-out", label: "Log out", onPress: handleLogout, destructive: true }],
    },
  ];

  return (
    <Screen edges={["top"]}>
      <ScrollView showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <View style={styles.avatar}>
            <Text variant="h1" color={colors.primary}>
              {user?.name?.charAt(0).toUpperCase() ?? "?"}
            </Text>
          </View>
          <View style={{ marginLeft: spacing.base, flex: 1 }}>
            <Text variant="h2" numberOfLines={1}>
              {user?.name ?? "Guest"}
            </Text>
            <Text variant="bodySmall" color={colors.textSecondary} numberOfLines={1}>
              {user?.email}
            </Text>
          </View>
        </View>

        {sections.map((section, sIdx) => (
          <View key={sIdx} style={styles.section}>
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
                {!item.destructive ? <Feather name="chevron-right" size={18} color={colors.textMuted} /> : null}
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
  header: { flexDirection: "row", alignItems: "center", padding: spacing.base, paddingTop: spacing.lg },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  section: {
    backgroundColor: colors.surface,
    marginHorizontal: spacing.base,
    marginTop: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.base,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  rowLast: { borderBottomWidth: 0 },
  rowLabel: { flex: 1, marginLeft: spacing.md },
  version: { marginTop: spacing["2xl"], marginBottom: spacing.xl },
});
