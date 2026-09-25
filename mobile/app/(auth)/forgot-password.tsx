import React, { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from "react-native";
import { Stack, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { TextField } from "@/components/TextField";
import { Button } from "@/components/Button";
import { authApi } from "@/api/authApi";
import { toApiError } from "@/api";
import { colors, radius, spacing } from "@/theme";
import { validateEmail, validatePassword } from "@/utils/validation";

type Step = "email" | "reset" | "done";

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("email");

  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState<string | undefined>();

  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [codeError, setCodeError] = useState<string | undefined>();
  const [passwordError, setPasswordError] = useState<string | undefined>();
  const [confirmError, setConfirmError] = useState<string | undefined>();

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleRequestCode = async () => {
    setError(null);
    const err = validateEmail(email) ?? undefined;
    setEmailError(err);
    if (err) return;

    setLoading(true);
    try {
      await authApi.forgotPassword(email.trim());
      // Always advances - the backend deliberately never reveals whether
      // the email is registered (enumeration protection), so this screen
      // can't either.
      setStep("reset");
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async () => {
    setError(null);
    const cErr = code.length === 6 && /^\d{6}$/.test(code) ? undefined : "Enter the 6-digit code";
    const pErr = validatePassword(newPassword) ?? undefined;
    const confErr = confirmPassword !== newPassword ? "Passwords don't match" : undefined;
    setCodeError(cErr);
    setPasswordError(pErr);
    setConfirmError(confErr);
    if (cErr || pErr || confErr) return;

    setLoading(true);
    try {
      await authApi.resetPassword({ email: email.trim(), code, new_password: newPassword });
      setStep("done");
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: "Forgot password" }} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.select({ ios: "padding", android: undefined })}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          {step === "email" && (
            <>
              <View style={styles.iconWrap}>
                <Feather name="mail" size={28} color={colors.primary} />
              </View>
              <Text variant="h3" style={styles.title}>
                Reset your password
              </Text>
              <Text variant="body" color={colors.textSecondary} style={styles.body}>
                Enter the email on your account and we'll send a 6-digit code to verify it's you.
              </Text>

              <TextField
                label="Email"
                placeholder="you@example.com"
                autoCapitalize="none"
                autoComplete="email"
                keyboardType="email-address"
                value={email}
                onChangeText={(v) => {
                  setEmail(v);
                  if (emailError) setEmailError(undefined);
                }}
                onSubmitEditing={handleRequestCode}
                error={emailError}
              />
              {error ? (
                <Text variant="bodySmall" color={colors.error} style={styles.error}>
                  {error}
                </Text>
              ) : null}
              <View style={{ height: spacing.xl }} />
              <Button label="Send code" onPress={handleRequestCode} loading={loading} fullWidth size="lg" />
            </>
          )}

          {step === "reset" && (
            <>
              <View style={styles.iconWrap}>
                <Feather name="shield" size={28} color={colors.primary} />
              </View>
              <Text variant="h3" style={styles.title}>
                Check your email
              </Text>
              <Text variant="body" color={colors.textSecondary} style={styles.body}>
                If an account exists for {email.trim()}, we've sent a 6-digit code. Enter it below
                with your new password.
              </Text>

              <TextField
                label="6-digit code"
                placeholder="123456"
                keyboardType="number-pad"
                maxLength={6}
                value={code}
                onChangeText={(v) => {
                  setCode(v.replace(/[^0-9]/g, ""));
                  if (codeError) setCodeError(undefined);
                }}
                error={codeError}
              />
              <View style={{ height: spacing.base }} />
              <TextField
                label="New password"
                placeholder="At least 8 characters"
                secureTextEntry
                autoCapitalize="none"
                autoComplete="new-password"
                value={newPassword}
                onChangeText={(v) => {
                  setNewPassword(v);
                  if (passwordError) setPasswordError(undefined);
                }}
                error={passwordError}
              />
              <View style={{ height: spacing.base }} />
              <TextField
                label="Confirm new password"
                placeholder="Re-enter your new password"
                secureTextEntry
                autoCapitalize="none"
                autoComplete="new-password"
                value={confirmPassword}
                onChangeText={(v) => {
                  setConfirmPassword(v);
                  if (confirmError) setConfirmError(undefined);
                }}
                onSubmitEditing={handleResetPassword}
                error={confirmError}
              />
              {error ? (
                <Text variant="bodySmall" color={colors.error} style={styles.error}>
                  {error}
                </Text>
              ) : null}
              <View style={{ height: spacing.xl }} />
              <Button label="Reset password" onPress={handleResetPassword} loading={loading} fullWidth size="lg" />
              <Button
                label="Use a different email"
                variant="outline"
                onPress={() => setStep("email")}
                fullWidth
                style={{ marginTop: spacing.md }}
              />
            </>
          )}

          {step === "done" && (
            <>
              <View style={styles.iconWrap}>
                <Feather name="check-circle" size={28} color={colors.primary} />
              </View>
              <Text variant="h3" style={styles.title}>
                Password reset
              </Text>
              <Text variant="body" color={colors.textSecondary} style={styles.body}>
                Your password has been changed. Please log in again with your new password - any
                other devices signed in to this account have been signed out.
              </Text>
              <View style={{ height: spacing.xl }} />
              <Button label="Back to login" onPress={() => router.replace("/(auth)/login")} fullWidth size="lg" />
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { flexGrow: 1, padding: spacing.xl, justifyContent: "center" },
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
  error: { marginTop: spacing.md },
});
