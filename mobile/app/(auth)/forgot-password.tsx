import React, { useState } from "react";
import { Pressable, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Text } from "@/components/Text";
import { TextField } from "@/components/TextField";
import { Button } from "@/components/Button";
import { useAuthStore } from "@/store/authStore";
import { authErrorMessage } from "@/auth/errors";
import { colors } from "@/theme";
import { validateEmail } from "@/utils/validation";
import { AuthScreen, ErrorBanner, NoticeBanner, authStyles } from "@/features/auth/AuthParts";
import { useCountdown } from "@/features/auth/PhoneSteps";

const RESEND_COOLDOWN_MS = 60_000;

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ email?: string }>();
  const forgotPassword = useAuthStore((s) => s.forgotPassword);
  const [email, setEmail] = useState(params.email ?? "");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const secondsLeft = useCountdown(cooldownUntil);

  const send = async () => {
    setError(null);
    const invalid = validateEmail(email);
    setFieldError(invalid);
    if (invalid) return;
    setSending(true);
    try {
      await forgotPassword(email);
      setSentTo(email.trim());
      setCooldownUntil(Date.now() + RESEND_COOLDOWN_MS);
    } catch (err) {
      setError(authErrorMessage(err, "Couldn't send the reset email. Please try again."));
    } finally {
      setSending(false);
    }
  };

  return (
    <AuthScreen title="Reset your password" subtitle="Enter your account email and we'll send you a link to choose a new password.">
      <TextField
        label="Email"
        placeholder="you@example.com"
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
        textContentType="emailAddress"
        value={email}
        onChangeText={(v) => {
          setEmail(v);
          if (fieldError) setFieldError(null);
        }}
        onSubmitEditing={send}
        error={fieldError}
      />
      {/* Same message whether or not the account exists (no account enumeration). */}
      <NoticeBanner
        message={
          sentTo
            ? `If an account exists for ${sentTo}, a reset link is on its way. The link expires after a while - request a new one if it stops working.`
            : null
        }
      />
      <ErrorBanner message={error} />
      <View style={authStyles.gapLg} />
      <Button
        label={secondsLeft > 0 ? `Resend in ${secondsLeft}s` : sentTo ? "Resend link" : "Send reset link"}
        onPress={send}
        loading={sending}
        disabled={secondsLeft > 0}
        fullWidth
        size="lg"
      />
      <View style={authStyles.footer}>
        <Pressable onPress={() => router.replace("/(auth)/login")} accessibilityRole="link" hitSlop={8}>
          <Text variant="bodyMedium" color={colors.primary}>
            Back to sign in
          </Text>
        </Pressable>
      </View>
    </AuthScreen>
  );
}
