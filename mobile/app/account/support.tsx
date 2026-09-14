import React from "react";
import { Linking, Pressable, StyleSheet, View } from "react-native";
import { Stack } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { colors, radius, spacing } from "@/theme";

/**
 * Static contact-based support (brief §35/§54: no in-app chat for MVP).
 * Email/phone are placeholders pending the client's real support
 * channels - never fabricated as if they were live/monitored.
 */
export default function SupportScreen() {
  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: "Support" }} />
      <View style={styles.content}>
        <Text variant="body" color={colors.textSecondary} style={styles.intro}>
          Need help with an order, a refund, or your account? Reach out and we'll get back to you.
        </Text>

        <Pressable style={styles.card} onPress={() => Linking.openURL("mailto:support@gawachabazaar.example")}>
          <Feather name="mail" size={18} color={colors.primary} />
          <Text variant="bodyMedium" style={{ marginLeft: spacing.md }}>
            support@gawachabazaar.example
          </Text>
        </Pressable>
        <Pressable style={styles.card} onPress={() => Linking.openURL("tel:+911234567890")}>
          <Feather name="phone" size={18} color={colors.primary} />
          <Text variant="bodyMedium" style={{ marginLeft: spacing.md }}>
            +91 12345 67890
          </Text>
        </Pressable>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.xl },
  intro: { marginBottom: spacing.xl },
  card: {
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
