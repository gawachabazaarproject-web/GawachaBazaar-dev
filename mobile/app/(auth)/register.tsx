import React, { useState } from "react";
import { View } from "react-native";
import { Link, useRouter } from "expo-router";
import { Text } from "@/components/Text";
import { TextField } from "@/components/TextField";
import { Button } from "@/components/Button";
import { useAuthStore } from "@/store/authStore";
import { authErrorMessage } from "@/auth/errors";
import { AccountExistsError } from "@/auth/types";
import { colors, spacing } from "@/theme";
import {
  validateEmail,
  validateNamePart,
  validatePasswordConfirmation,
  validateStrongPassword,
} from "@/utils/validation";
import { AuthScreen, ErrorBanner, GoogleButton, OrDivider, PhoneButton, authStyles } from "@/features/auth/AuthParts";

type Field = "firstName" | "lastName" | "email" | "password" | "confirm";
type FieldErrors = Partial<Record<Field, string>>;

export default function RegisterScreen() {
  const router = useRouter();
  const register = useAuthStore((s) => s.register);
  const loginWithGoogle = useAuthStore((s) => s.loginWithGoogle);
  const [values, setValues] = useState<Record<Field, string>>({
    firstName: "",
    lastName: "",
    email: "",
    password: "",
    confirm: "",
  });
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<"email" | "google" | null>(null);

  const update = (field: Field) => (v: string) => {
    setValues((s) => ({ ...s, [field]: v }));
    if (fieldErrors[field]) setFieldErrors((e) => ({ ...e, [field]: undefined }));
  };

  const handleRegister = async () => {
    setError(null);
    const errors: FieldErrors = {
      firstName: validateNamePart(values.firstName, "First name") ?? undefined,
      lastName: validateNamePart(values.lastName, "Last name") ?? undefined,
      email: validateEmail(values.email) ?? undefined,
      password: validateStrongPassword(values.password) ?? undefined,
      confirm: validatePasswordConfirmation(values.password, values.confirm) ?? undefined,
    };
    setFieldErrors(errors);
    if (Object.values(errors).some(Boolean)) return;

    setLoading("email");
    try {
      await register({
        firstName: values.firstName,
        lastName: values.lastName,
        email: values.email,
        password: values.password,
      });
      // AppGate moves to the verify-email screen.
    } catch (err) {
      setError(authErrorMessage(err, "Couldn't create your account. Please try again."));
    } finally {
      setLoading(null);
    }
  };

  const handleGoogle = async () => {
    setError(null);
    setLoading("google");
    try {
      await loginWithGoogle();
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
    <AuthScreen title="Create your account" subtitle="Farm-fresh produce, straight to your door.">
      <View style={{ flexDirection: "row", gap: spacing.md }}>
        <View style={{ flex: 1 }}>
          <TextField
            label="First name"
            placeholder="Arjun"
            autoComplete="given-name"
            textContentType="givenName"
            value={values.firstName}
            onChangeText={update("firstName")}
            error={fieldErrors.firstName}
          />
        </View>
        <View style={{ flex: 1 }}>
          <TextField
            label="Last name"
            placeholder="Sharma"
            autoComplete="family-name"
            textContentType="familyName"
            value={values.lastName}
            onChangeText={update("lastName")}
            error={fieldErrors.lastName}
          />
        </View>
      </View>
      <View style={authStyles.gap} />
      <TextField
        label="Email"
        placeholder="you@example.com"
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
        textContentType="emailAddress"
        value={values.email}
        onChangeText={update("email")}
        error={fieldErrors.email}
      />
      <View style={authStyles.gap} />
      <TextField
        label="Password"
        placeholder="At least 8 characters"
        secureTextEntry
        autoComplete="new-password"
        textContentType="newPassword"
        value={values.password}
        onChangeText={update("password")}
        error={fieldErrors.password}
        helperText="8+ characters with upper and lowercase letters and a number."
      />
      <View style={authStyles.gap} />
      <TextField
        label="Confirm password"
        placeholder="Re-enter your password"
        secureTextEntry
        autoComplete="new-password"
        textContentType="newPassword"
        value={values.confirm}
        onChangeText={update("confirm")}
        onSubmitEditing={handleRegister}
        error={fieldErrors.confirm}
      />

      <ErrorBanner message={error} />
      <View style={authStyles.gapLg} />
      <Button label="Create Account" onPress={handleRegister} loading={loading === "email"} disabled={loading === "google"} fullWidth size="lg" />

      <OrDivider />
      <GoogleButton onPress={handleGoogle} loading={loading === "google"} disabled={loading === "email"} />
      <View style={authStyles.gap} />
      <PhoneButton onPress={() => router.push("/(auth)/phone")} disabled={loading !== null} />

      <View style={authStyles.footer}>
        <Text variant="body" color={colors.textSecondary}>
          Already have an account?{" "}
        </Text>
        <Link href="/(auth)/login" asChild>
          <Text variant="bodyMedium" color={colors.primary}>
            Sign in
          </Text>
        </Link>
      </View>
    </AuthScreen>
  );
}
