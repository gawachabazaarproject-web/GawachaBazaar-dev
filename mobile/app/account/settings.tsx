import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Stack, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { colors, spacing } from "@/theme";

export default function SettingsScreen() {
  const router = useRouter();
  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: "Settings" }} />
      <View style={styles.content}>
        <Row label="Terms & Conditions" icon="file-text" onPress={() => router.push("/account/legal/terms" as never)} />
        <Row label="Privacy Policy" icon="shield" onPress={() => router.push("/account/legal/privacy" as never)} />
        <Row label="All policies" icon="book-open" onPress={() => router.push("/account/legal" as never)} last />
      </View>
    </Screen>
  );
}

function Row({
  label,
  icon,
  last,
  onPress,
}: {
  label: string;
  icon: keyof typeof Feather.glyphMap;
  last?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable style={[styles.row, last && styles.rowLast]} onPress={onPress}>
      <Feather name={icon} size={18} color={colors.textSecondary} />
      <Text variant="bodyLarge" style={{ marginLeft: spacing.md, flex: 1 }}>
        {label}
      </Text>
      <Feather name="arrow-up-right" size={16} color={colors.textMuted} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.xl },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderColor: colors.divider,
  },
  rowLast: { borderBottomWidth: 0 },
});
