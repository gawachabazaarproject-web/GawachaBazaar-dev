import React, { useCallback, useEffect, useState } from "react";
import { AppState, Pressable, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { useAuthStore } from "@/store/authStore";
import { authErrorMessage } from "@/auth/errors";
import { colors, spacing } from "@/theme";
import { AuthScreen, ErrorBanner, NoticeBanner, authStyles } from "@/features/auth/AuthParts";
import { useCountdown } from "@/features/auth/PhoneSteps";

export default function VerifyEmailScreen() {
  const email = useAuthStore((s) => s.firebaseUser?.email ?? s.user?.email ?? null);
  const refreshUser = useAuthStore((s) => s.refreshUser);
  const resendVerificationEmail = useAuthStore((s) => s.resendVerificationEmail);
  const logout = useAuthStore((s) => s.logout);
  const cooldownUntil = useAuthStore((s) => s.verificationEmailCooldownUntil);
  const secondsLeft = useCountdown(cooldownUntil);
  const [checking, setChecking] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const check = useCallback(
    async (manual: boolean) => {
      if (manual) {
        setError(null);
        setNotice(null);
        setChecking(true);
      }
      try {
        const verified = await refreshUser();
        // Verified -> AppGate navigates on. Otherwise only a manual
        // check deserves a message.
        if (!verified && manual) setError("Your email isn't verified yet. Open the link we sent, then try again.");
      } catch (err) {
        if (manual) setError(authErrorMessage(err));
      } finally {
        if (manual) setChecking(false);
      }
    },
    [refreshUser],
  );

  // Coming back from the mail app is the usual moment the link was clicked.
  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") void check(false);
    });
    return () => sub.remove();
  }, [check]);

  const resend = async () => {
    setError(null);
    setNotice(null);
    setSending(true);
    try {
      await resendVerificationEmail();
      setNotice("A new verification link is on its way. Check your inbox and spam folder.");
    } catch (err) {
      setError(authErrorMessage(err, "Couldn't send the email. Please try again."));
    } finally {
      setSending(false);
    }
  };

  return (
    <AuthScreen title="Verify your email">
      <View style={{ alignItems: "center", marginBottom: spacing.xl }}>
        <Ionicons name="mail-unread-outline" size={56} color={colors.primary} />
        <Text variant="body" color={colors.textSecondary} align="center" style={{ marginTop: spacing.base }}>
          We sent a verification link to{"\n"}
          <Text variant="bodyMedium">{email ?? "your email"}</Text>
          {"\n"}Open it to activate your account.
        </Text>
      </View>

      <Button label="I've verified my email" onPress={() => check(true)} loading={checking} fullWidth size="lg" />
      <View style={authStyles.gap} />
      <Button
        label={secondsLeft > 0 ? `Resend email in ${secondsLeft}s` : "Resend verification email"}
        variant="outline"
        onPress={resend}
        loading={sending}
        disabled={secondsLeft > 0}
        fullWidth
        size="lg"
      />

      <NoticeBanner message={notice} />
      <ErrorBanner message={error} />

      <Text variant="bodySmall" color={colors.textMuted} align="center" style={{ marginTop: spacing.xl }}>
        Link expired or not working? Resend it - only the newest link works.
      </Text>

      <View style={authStyles.footer}>
        <Pressable onPress={logout} accessibilityRole="button" hitSlop={8}>
          <Text variant="bodyMedium" color={colors.primary}>
            Use a different account (log out)
          </Text>
        </Pressable>
      </View>
    </AuthScreen>
  );
}
