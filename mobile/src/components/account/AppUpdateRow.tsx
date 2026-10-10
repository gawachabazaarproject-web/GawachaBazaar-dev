import React from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "../Text";
import { useAppUpdates, UpdateStatus } from "@/features/updates/useAppUpdates";
import { colors, fontFamily, spacing } from "@/theme";

const STATUS_TEXT: Record<UpdateStatus, string> = {
  idle: "Tap to check",
  checking: "Checking...",
  downloading: "Downloading update...",
  "up-to-date": "You're up to date",
  ready: "Update ready - restart",
  unavailable: "Not available in development builds",
  error: "Couldn't check - tap to retry",
};

/**
 * "Check for updates" row for the Account screen. The app also checks on its
 * own every time it starts; this is for people who want the latest version
 * right now without closing the app.
 */
export function AppUpdateRow() {
  const { status, check, restart } = useAppUpdates();
  const busy = status === "checking" || status === "downloading";
  const disabled = busy || status === "unavailable";

  const promptRestart = () =>
    Alert.alert("Update ready", "A new version has been downloaded. Restart GawachaBazaar to use it?", [
      { text: "Later", style: "cancel" },
      { text: "Restart now", onPress: () => void restart() },
    ]);

  const handlePress = async () => {
    if (status === "ready") {
      promptRestart();
      return;
    }
    if (await check()) promptRestart();
  };

  return (
    <View style={styles.card}>
      <Pressable
        style={styles.row}
        onPress={handlePress}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel="Check for updates"
      >
        <View style={styles.tile}>
          <Feather name="refresh-cw" size={19} color={colors.primary} />
        </View>
        <View style={styles.text}>
          <Text variant="bodyLarge" color={colors.textPrimary} style={styles.label}>
            Check for updates
          </Text>
          <Text variant="caption" color={status === "ready" ? colors.success : colors.textSecondary}>
            {STATUS_TEXT[status]}
          </Text>
        </View>
        {busy ? (
          <ActivityIndicator size="small" color={colors.primary} />
        ) : status === "unavailable" ? null : (
          <Feather name="chevron-right" size={18} color={colors.textPrimary} />
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginHorizontal: spacing.base,
    marginTop: spacing.xl,
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
  tile: {
    width: 38,
    height: 38,
    borderRadius: 11,
    backgroundColor: colors.successLight,
    alignItems: "center",
    justifyContent: "center",
  },
  text: { flex: 1 },
  label: { fontFamily: fontFamily.medium, fontSize: 15 },
});
