import React from "react";
import { Linking, Pressable, StyleSheet, View } from "react-native";
import { Stack, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { colors, radius, spacing } from "@/theme";

/**
 * The backend has no password-reset endpoint (see mobile/README.md Known
 * Limitations). Rather than fake a working reset flow, this screen is
 * honest about the gap and routes to support instead.
 */
export default function ForgotPasswordScreen() {
  const router = useRouter();

  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: "Forgot password" }} />
      <View style={styles.content}>
        <View style={styles.iconWrap}>
          <Feather name="lock" size={28} color={colors.primary} />
        </View>
        <Text variant="h3" style={styles.title}>
          We can't reset your password automatically yet
        </Text>
        <Text variant="body" color={colors.textSecondary} style={styles.body}>
          Self-service password reset isn't available in the app yet. Contact support with your
          registered email or phone number and we'll help you regain access to your account.
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

        <View style={{ height: spacing.xl }} />
        <Button label="Back to login" variant="outline" onPress={() => router.back()} fullWidth />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { flexGrow: 1, padding: spacing.xl },
  iconWrap: {
    width: 56,
    height: 56,
    borderRadius: radius.pill,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
  },
  title: { marginBottom: spacing.md },
  body: { marginBottom: spacing.xl },
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
