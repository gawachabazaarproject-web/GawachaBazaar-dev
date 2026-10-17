import React, { useState } from "react";
import { Pressable, View } from "react-native";
import { Link, useRouter } from "expo-router";
import { Text } from "@/components/Text";
import { useAuthStore } from "@/store/authStore";
import { authErrorMessage } from "@/auth/errors";
import { AccountExistsError } from "@/auth/types";
import { colors, fontFamily } from "@/theme";
import { validateEmail } from "@/utils/validation";
import { ErrorBanner } from "@/features/auth/AuthParts";
import {
  LoginField,
  LoginGoogleButton,
  LoginOrDivider,
  LoginShell,
  LoginSubmitButton,
  useLoginScale,
} from "@/features/auth/LoginParts";

type FieldErrors = { email?: string; password?: string };

export default function LoginScreen() {
  const router = useRouter();
  const s = useLoginScale();
  const login = useAuthStore((st) => st.login);
  const loginWithGoogle = useAuthStore((st) => st.loginWithGoogle);
  const authError = useAuthStore((st) => st.authError);
  const linkEmail = useAuthStore((st) => st.linkEmail);
  const clearAuthError = useAuthStore((st) => st.clearAuthError);
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
    <LoginShell>
      <LoginGoogleButton onPress={handleGoogle} loading={loading === "google"} disabled={loading === "email"} />

      <LoginOrDivider />

      <LoginField
        label="Email"
        icon="mail"
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
      <View style={{ height: 52 * s }} />
      <LoginField
        label="Password"
        icon="lock"
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
      <View style={{ alignItems: "flex-end", marginTop: 26 * s }}>
        <Link href={{ pathname: "/(auth)/forgot-password", params: email ? { email } : {} }} asChild>
          <Pressable accessibilityRole="link" hitSlop={8}>
            <Text style={{ fontFamily: fontFamily.semibold, fontSize: 30 * s, color: colors.primary }}>
              Forgot password?
            </Text>
          </Pressable>
        </Link>
      </View>

      <ErrorBanner message={error ?? authError} />
      <View style={{ height: 52 * s }} />
      <LoginSubmitButton label="Sign in" onPress={handleLogin} loading={loading === "email"} disabled={loading === "google"} />

      <View style={{ flexDirection: "row", justifyContent: "center", flexWrap: "wrap", marginTop: 50 * s, marginBottom: 40 * s }}>
        <Text style={{ fontFamily: fontFamily.regular, fontSize: 31 * s, color: colors.textSecondary }}>
          Don&apos;t have an account?{" "}
        </Text>
        <Link href="/(auth)/register" asChild>
          <Text style={{ fontFamily: fontFamily.bold, fontSize: 31 * s, color: colors.primary }}>Create account</Text>
        </Link>
      </View>
    </LoginShell>
  );
}
