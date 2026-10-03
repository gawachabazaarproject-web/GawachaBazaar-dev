import React, { useState } from "react";
import { Pressable, View } from "react-native";
import { Link, useRouter } from "expo-router";
import { Text } from "@/components/Text";
import { TextField } from "@/components/TextField";
import { Button } from "@/components/Button";
import { useAuthStore } from "@/store/authStore";
import { authErrorMessage } from "@/auth/errors";
import { AccountExistsError } from "@/auth/types";
import { colors } from "@/theme";
import { validateEmail } from "@/utils/validation";
import { AuthScreen, ErrorBanner, GoogleButton, OrDivider, PhoneButton, authStyles } from "@/features/auth/AuthParts";

type FieldErrors = { email?: string; password?: string };

export default function LoginScreen() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const loginWithGoogle = useAuthStore((s) => s.loginWithGoogle);
  const authError = useAuthStore((s) => s.authError);
  const linkEmail = useAuthStore((s) => s.linkEmail);
  const clearAuthError = useAuthStore((s) => s.clearAuthError);
  const [email, setEmail] = useState(linkEmail ?? "");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<"email" | "google" | null>(null);

  const handleLogin = async () => {
    setError(null);
    clearAuthError();
    const errors: FieldErrors = {
      email: validateEmail(email) ?? undefined,
      password: password ? undefined : "Enter your password.",
    };
    setFieldErrors(errors);
    if (errors.email || errors.password) return;

    setLoading("email");
    try {
      await login(email, password);
      // AppGate redirects once the session settles.
    } catch (err) {
      setError(authErrorMessage(err, "Unable to log in. Please try again."));
    } finally {
      setLoading(null);
    }
  };

  const handleGoogle = async () => {
    setError(null);
    clearAuthError();
    setLoading("google");
    try {
      await loginWithGoogle(); // "cancelled" needs no message
    } catch (err) {
      if (err instanceof AccountExistsError) {
        router.push("/(auth)/link-account");
        return;
      }
      setError(authErrorMessage(err, "Google sign-in failed. Please try again."));
    } finally {
      setLoading(null);
    }
  };

  return (
    <AuthScreen showWordmark subtitle="Fresh groceries, delivered fast.">
      <GoogleButton onPress={handleGoogle} loading={loading === "google"} disabled={loading === "email"} />

      <OrDivider />

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
          if (fieldErrors.email) setFieldErrors((e) => ({ ...e, email: undefined }));
        }}
        error={fieldErrors.email}
      />
      <View style={authStyles.gap} />
      <TextField
        label="Password"
        placeholder="Your password"
        secureTextEntry
        autoComplete="current-password"
        textContentType="password"
        value={password}
        onChangeText={(v) => {
          setPassword(v);
          if (fieldErrors.password) setFieldErrors((e) => ({ ...e, password: undefined }));
        }}
        onSubmitEditing={handleLogin}
        error={fieldErrors.password}
      />
      <View style={authStyles.linkRow}>
        <Link href={{ pathname: "/(auth)/forgot-password", params: email ? { email } : {} }} asChild>
          <Pressable accessibilityRole="link" hitSlop={8}>
            <Text variant="bodyMedium" color={colors.primary}>
              Forgot password?
            </Text>
          </Pressable>
        </Link>
      </View>

      <ErrorBanner message={error ?? authError} />
      <View style={authStyles.gapLg} />
      <Button label="Sign in" onPress={handleLogin} loading={loading === "email"} disabled={loading === "google"} fullWidth size="lg" />

      <View style={authStyles.footer}>
        <Text variant="body" color={colors.textSecondary}>
          Don&apos;t have an account?{" "}
        </Text>
        <Link href="/(auth)/register" asChild>
          <Text variant="bodyMedium" color={colors.primary}>
            Create account
          </Text>
        </Link>
      </View>

      <OrDivider />
      <PhoneButton onPress={() => router.push("/(auth)/phone")} disabled={loading !== null} />
    </AuthScreen>
  );
}
