import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Stack } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { colors, radius, spacing } from "@/theme";

export default function SettingsScreen() {
  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: "Settings" }} />
      <View style={styles.content}>
        <Row label="About GawachaBazaar" icon="info" />
        <Row label="Terms of service" icon="file-text" />
        <Row label="Privacy policy" icon="shield" />
      </View>
    </Screen>
  );
}

function Row({ label, icon }: { label: string; icon: keyof typeof Feather.glyphMap }) {
  return (
    <Pressable style={styles.row}>
      <Feather name={icon} size={18} color={colors.textSecondary} />
      <Text variant="bodyLarge" style={{ marginLeft: spacing.md, flex: 1 }}>
        {label}
      </Text>
      <Feather name="chevron-right" size={18} color={colors.textMuted} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.xl },
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.base,
    marginBottom: spacing.md,
  },
});
