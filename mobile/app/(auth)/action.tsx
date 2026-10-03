import React, { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { TextField } from "@/components/TextField";
import { Button } from "@/components/Button";
import { applyActionCode, confirmPasswordReset, verifyPasswordResetCode } from "@/auth/firebase";
import { authErrorMessage } from "@/auth/errors";
import { useAuthStore } from "@/store/authStore";
import { colors, spacing } from "@/theme";
import { validatePasswordConfirmation, validateStrongPassword } from "@/utils/validation";
import { AuthScreen, ErrorBanner, authStyles } from "@/features/auth/AuthParts";

/**
 * Handles Firebase email action links in-app: `/action?mode=resetPassword|
 * verifyEmail&oobCode=...` (Reset Password + email verification). Only used
 * when Firebase Console -> Authentication -> Templates -> "Customize action
 * URL" points here; otherwise Firebase's hosted page handles the link and
 * the customer returns to the app themselves.
 */
type Phase = "checking" | "form" | "done" | "failed";

export default function EmailActionScreen() {
  const router = useRouter();
  const { mode, oobCode } = useLocalSearchParams<{ mode?: string; oobCode?: string }>();
  const status = useAuthStore((s) => s.status);
  const refreshUser = useAuthStore((s) => s.refreshUser);
  const [phase, setPhase] = useState<Phase>("checking");
  const [email, setEmail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ password?: string; confirm?: string }>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!oobCode) {
      setError("This link is invalid or has already been used.");
      setPhase("failed");
      return;
    }
    (async () => {
      try {
        if (mode === "resetPassword") {
          setEmail(await verifyPasswordResetCode(oobCode));
          setPhase("form");
        } else if (mode === "verifyEmail") {
          await applyActionCode(oobCode);
          if (status === "verifyingEmail") await refreshUser().catch(() => undefined);
          setPhase("done");
        } else {
          setError("This link isn't supported.");
          setPhase("failed");
        }
      } catch (err) {
        setError(authErrorMessage(err, "This link is invalid or has expired."));
        setPhase("failed");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, oobCode]);

  const save = async () => {
    const errors = {
      password: validateStrongPassword(password) ?? undefined,
      confirm: validatePasswordConfirmation(password, confirm) ?? undefined,
    };
    setFieldErrors(errors);
    if (errors.password || errors.confirm || !oobCode) return;
    setError(null);
    setSaving(true);
    try {
      await confirmPasswordReset(oobCode, password);
      setPhase("done");
    } catch (err) {
      setError(authErrorMessage(err, "Couldn't update your password. Request a new link."));
    } finally {
      setSaving(false);
    }
  };

  if (phase === "checking") {
    return (
      <AuthScreen>
        <ActivityIndicator color={colors.primary} />
      </AuthScreen>
    );
  }

  if (phase === "failed") {
    return (
      <AuthScreen title="Link not valid">
        <ErrorBanner message={error} />
        <View style={authStyles.gapLg} />
        <Button
          label={mode === "resetPassword" ? "Request a new reset link" : "Back to sign in"}
          onPress={() => router.replace(mode === "resetPassword" ? "/(auth)/forgot-password" : "/(auth)/login")}
          fullWidth
          size="lg"
        />
      </AuthScreen>
    );
  }

  if (phase === "done") {
    const reset = mode === "resetPassword";
    return (
      <AuthScreen title={reset ? "Password updated" : "Email verified"}>
        <View style={{ alignItems: "center", marginBottom: spacing.xl }}>
          <Ionicons name="checkmark-circle" size={56} color={colors.success} />
          <Text variant="body" color={colors.textSecondary} align="center" style={{ marginTop: spacing.base }}>
            {reset ? "You can now sign in with your new password." : "Thanks - your email address is confirmed."}
          </Text>
        </View>
        <Button label={reset ? "Sign in" : "Continue"} onPress={() => router.replace("/(auth)/login")} fullWidth size="lg" />
      </AuthScreen>
    );
  }

  return (
    <AuthScreen title="Choose a new password" subtitle={email ? `For ${email}` : undefined}>
      <TextField
        label="New password"
        secureTextEntry
        autoComplete="new-password"
        textContentType="newPassword"
        value={password}
        onChangeText={setPassword}
        error={fieldErrors.password}
        helperText="8+ characters with upper and lowercase letters and a number."
      />
      <View style={authStyles.gap} />
      <TextField
        label="Confirm new password"
        secureTextEntry
        autoComplete="new-password"
        value={confirm}
        onChangeText={setConfirm}
        onSubmitEditing={save}
        error={fieldErrors.confirm}
      />
      <ErrorBanner message={error} />
      <View style={authStyles.gapLg} />
      <Button label="Update password" onPress={save} loading={saving} fullWidth size="lg" />
    </AuthScreen>
  );
}
