import React, { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { TextField } from "@/components/TextField";
import { Button } from "@/components/Button";
import { useAuthStore } from "@/store/authStore";
import { toApiError } from "@/api";
import { colors, spacing } from "@/theme";

export default function VerifyOtpScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ challengeToken: string; maskedEmail: string }>();
  const verifyOtp = useAuthStore((s) => s.verifyOtp);

  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleVerify = async () => {
    setError(null);
    if (!/^\d{6}$/.test(code)) {
      setError("Enter the 6-digit code.");
      return;
    }
    setLoading(true);
    try {
      await verifyOtp(params.challengeToken, code);
      // AppGate handles the redirect once `status` flips to authenticated.
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.select({ ios: "padding", android: undefined })}
      >
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.header}>
            <Text variant="h2">Check your email</Text>
            <Text variant="body" color={colors.textSecondary} style={styles.subtitle}>
              We sent a 6-digit code to {params.maskedEmail || "your registered email"}. Enter it
              below to finish signing in.
            </Text>
          </View>

          <TextField
            label="Verification code"
            placeholder="123456"
            keyboardType="number-pad"
            maxLength={6}
            autoFocus
            value={code}
            onChangeText={(v) => {
              setCode(v.replace(/\D/g, ""));
              if (error) setError(null);
            }}
            onSubmitEditing={handleVerify}
            error={error}
          />

          <View style={{ height: spacing.xl }} />
          <Button label="Verify & continue" onPress={handleVerify} loading={loading} fullWidth size="lg" />

          <Text
            variant="bodyMedium"
            color={colors.primary}
            style={styles.backLink}
            onPress={() => router.replace("/(auth)/login")}
          >
            Back to login
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { flexGrow: 1, padding: spacing.xl, justifyContent: "center" },
  header: { marginBottom: spacing["2xl"] },
  subtitle: { marginTop: spacing.sm },
  backLink: { textAlign: "center", marginTop: spacing["2xl"] },
});
