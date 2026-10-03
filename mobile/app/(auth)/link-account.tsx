import React, { useState } from "react";
import { Pressable, View } from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { TextField } from "@/components/TextField";
import { Button } from "@/components/Button";
import { useAuthStore } from "@/store/authStore";
import { hasPendingCredential } from "@/auth/firebase";
import { authErrorMessage } from "@/auth/errors";
import { colors, spacing } from "@/theme";
import { AuthScreen, ErrorBanner, PhoneButton, authStyles } from "@/features/auth/AuthParts";

/**
 * "You already have an account": the email of the Google (or other) sign-in
 * that was just attempted belongs to an existing account that uses another
 * method. The customer proves ownership by signing in the original way;
 * if a Google credential is pending it is then linked to that same
 * account, so one customer keeps one account.
 */
export default function LinkAccountScreen() {
  const router = useRouter();
  const linkEmail = useAuthStore((s) => s.linkEmail);
  const authError = useAuthStore((s) => s.authError);
  const login = useAuthStore((s) => s.login);
  const clearAuthError = useAuthStore((s) => s.clearAuthError);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const googlePending = hasPendingCredential();

  const signIn = async () => {
    if (!linkEmail || !password) {
      setError("Enter your password.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await login(linkEmail, password); // links the pending Google credential
    } catch (err) {
      setError(authErrorMessage(err, "Unable to sign in. Please try again."));
    } finally {
      setLoading(false);
    }
  };

  const back = () => {
    clearAuthError();
    router.replace("/(auth)/login");
  };

  return (
    <AuthScreen title="You already have an account">
      <View style={{ alignItems: "center", marginBottom: spacing.xl }}>
        <Ionicons name="link-outline" size={48} color={colors.primary} />
        <Text variant="body" color={colors.textSecondary} align="center" style={{ marginTop: spacing.base }}>
          {linkEmail ? (
            <>
              <Text variant="bodyMedium">{linkEmail}</Text> is already registered with a different sign-in method.
            </>
          ) : (
            "These details are already registered with a different sign-in method."
          )}{" "}
          Sign in the way you did before
          {googlePending ? " and we'll connect Google to the same account." : ", then add this method from your account."}
        </Text>
      </View>

      {linkEmail ? (
        <>
          <TextField label="Email" value={linkEmail} editable={false} />
          <View style={authStyles.gap} />
          <TextField
            label="Password"
            placeholder="Your password"
            secureTextEntry
            autoComplete="current-password"
            value={password}
            onChangeText={setPassword}
            onSubmitEditing={signIn}
          />
          <ErrorBanner message={error ?? authError} />
          <View style={authStyles.gapLg} />
          <Button label={googlePending ? "Sign in and link Google" : "Sign in"} onPress={signIn} loading={loading} fullWidth size="lg" />
          <View style={authStyles.linkRow}>
            <Pressable
              onPress={() => router.push({ pathname: "/(auth)/forgot-password", params: { email: linkEmail } })}
              accessibilityRole="link"
              hitSlop={8}
            >
              <Text variant="bodyMedium" color={colors.primary}>
                Forgot password?
              </Text>
            </Pressable>
          </View>
          <View style={authStyles.gap} />
        </>
      ) : (
        <ErrorBanner message={authError} />
      )}

      <View style={authStyles.gap} />
      <PhoneButton onPress={() => router.push("/(auth)/phone")} />

      <View style={authStyles.footer}>
        <Pressable onPress={back} accessibilityRole="link" hitSlop={8}>
          <Text variant="bodyMedium" color={colors.primary}>
            Back to sign in
          </Text>
        </Pressable>
      </View>
    </AuthScreen>
  );
}
