import React from "react";
import { View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { firebaseConfigured } from "@/auth/firebase";
import { useAuthStore } from "@/store/authStore";
import { colors, spacing } from "@/theme";
import { AuthScreen } from "@/features/auth/AuthParts";

/** Shown when sign-in can't work at all (Firebase missing from this build)
 * or for an explicit `?message=`. Never shows raw error details. */
export default function AuthErrorScreen() {
  const router = useRouter();
  const { message } = useLocalSearchParams<{ message?: string }>();
  const authError = useAuthStore((s) => s.authError);
  const clearAuthError = useAuthStore((s) => s.clearAuthError);

  const text = !firebaseConfigured
    ? "Sign-in isn't available in this version of the app. Please update the app or try again later."
    : message ?? authError ?? "Something went wrong while signing you in. Please try again.";

  return (
    <AuthScreen title="We couldn't sign you in">
      <View style={{ alignItems: "center", marginBottom: spacing.xl }}>
        <Ionicons name="cloud-offline-outline" size={56} color={colors.error} />
        <Text variant="body" color={colors.textSecondary} align="center" style={{ marginTop: spacing.base }}>
          {text}
        </Text>
      </View>
      {firebaseConfigured ? (
        <Button
          label="Back to sign in"
          onPress={() => {
            clearAuthError();
            router.replace("/(auth)/login");
          }}
          fullWidth
          size="lg"
        />
      ) : null}
    </AuthScreen>
  );
}
