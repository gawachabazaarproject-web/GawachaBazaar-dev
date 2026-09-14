import React, { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from "react-native";
import { Link, useRouter } from "expo-router";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { TextField } from "@/components/TextField";
import { Button } from "@/components/Button";
import { Wordmark } from "@/components/Wordmark";
import { useAuthStore } from "@/store/authStore";
import { toApiError } from "@/api";
import { colors, spacing } from "@/theme";
import { validateLoginIdentifier, validatePassword } from "@/utils/validation";

type FieldErrors = { identifier?: string; password?: string };

export default function LoginScreen() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setError(null);
    const errors: FieldErrors = {
      identifier: validateLoginIdentifier(identifier) ?? undefined,
      password: validatePassword(password) ?? undefined,
    };
    setFieldErrors(errors);
    if (errors.identifier || errors.password) return;

    setLoading(true);
    try {
      await login(identifier.trim(), password);
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
            <Wordmark />
            <Text variant="body" color={colors.textSecondary} style={styles.subtitle}>
              Fresh groceries, delivered fast.
            </Text>
          </View>

          <View style={styles.form}>
            <TextField
              label="Email or phone"
              placeholder="you@example.com"
              autoCapitalize="none"
              autoComplete="username"
              keyboardType="email-address"
              value={identifier}
              onChangeText={(v) => {
                setIdentifier(v);
                if (fieldErrors.identifier) setFieldErrors((e) => ({ ...e, identifier: undefined }));
              }}
              error={fieldErrors.identifier}
            />
            <View style={{ height: spacing.base }} />
            <TextField
              label="Password"
              placeholder="Your password"
              secureTextEntry
              autoComplete="current-password"
              value={password}
              onChangeText={(v) => {
                setPassword(v);
                if (fieldErrors.password) setFieldErrors((e) => ({ ...e, password: undefined }));
              }}
              onSubmitEditing={handleLogin}
              error={fieldErrors.password}
            />
            <Link href="/(auth)/forgot-password" asChild>
              <Text variant="bodySmall" color={colors.primary} style={styles.forgotLink}>
                Forgot password?
              </Text>
            </Link>
            {error ? (
              <Text variant="bodySmall" color={colors.error} style={styles.error}>
                {error}
              </Text>
            ) : null}
            <View style={{ height: spacing.xl }} />
            <Button label="Log in" onPress={handleLogin} loading={loading} fullWidth size="lg" />
          </View>

          <View style={styles.footer}>
            <Text variant="body" color={colors.textSecondary}>
              New to GawachaBazaar?{" "}
            </Text>
            <Link href="/(auth)/register" asChild>
              <Text variant="bodyMedium" color={colors.primary}>
                Create an account
              </Text>
            </Link>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { flexGrow: 1, padding: spacing.xl, justifyContent: "center" },
  header: { marginBottom: spacing["3xl"], alignItems: "flex-start" },
  subtitle: { marginTop: spacing.sm },
  form: {},
  forgotLink: { alignSelf: "flex-end", marginTop: spacing.sm },
  error: { marginTop: spacing.md },
  footer: { flexDirection: "row", justifyContent: "center", marginTop: spacing["2xl"] },
});
