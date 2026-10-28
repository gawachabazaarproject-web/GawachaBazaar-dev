import React from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Stack, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { POLICIES } from "@/features/legal/content";
import { colors, spacing } from "@/theme";

export default function LegalIndexScreen() {
  const router = useRouter();
  return (
    <Screen edges={["bottom"]}>
      <Stack.Screen options={{ headerShown: true, title: "Policies" }} />
      <ScrollView contentContainerStyle={styles.content}>
        {POLICIES.map((p, i) => (
          <Pressable
            key={p.slug}
            style={[styles.row, i === POLICIES.length - 1 && styles.rowLast]}
            onPress={() => router.push(`/account/legal/${p.slug}` as never)}
          >
            <Text variant="bodyLarge" style={{ flex: 1 }}>
              {p.menuLabel}
            </Text>
            <Feather name="chevron-right" size={18} color={colors.textMuted} />
          </Pressable>
        ))}
        <View style={{ height: spacing.xl }} />
      </ScrollView>
    </Screen>
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
