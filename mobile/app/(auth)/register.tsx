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
import { validateEmail, validateName, validatePassword, validatePhone } from "@/utils/validation";

type FieldErrors = { name?: string; email?: string; phone?: string; password?: string };

export default function RegisterScreen() {
  const router = useRouter();
  const register = useAuthStore((s) => s.register);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const setField =
    (key: keyof FieldErrors, setter: (v: string) => void) =>
    (v: string) => {
      setter(v);
      if (fieldErrors[key]) setFieldErrors((e) => ({ ...e, [key]: undefined }));
    };

  const handleRegister = async () => {
    setError(null);
    const errors: FieldErrors = {
      name: validateName(name) ?? undefined,
      email: validateEmail(email) ?? undefined,
      phone: validatePhone(phone) ?? undefined,
      password: validatePassword(password) ?? undefined,
    };
    setFieldErrors(errors);
    if (Object.values(errors).some(Boolean)) return;

    setLoading(true);
    try {
      await register({ name: name.trim(), email: email.trim(), phone: phone.trim(), password });
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.select({ ios: "padding", android: undefined })}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.header}>
            <Wordmark size="md" />
            <Text variant="h2" style={styles.title}>
              Create your account
            </Text>
          </View>

          <TextField
            label="Full name"
            placeholder="Priya Sharma"
            value={name}
            onChangeText={setField("name", setName)}
            autoComplete="name"
            error={fieldErrors.name}
          />
          <View style={{ height: spacing.base }} />
          <TextField
            label="Email"
            placeholder="you@example.com"
            autoCapitalize="none"
            keyboardType="email-address"
            autoComplete="email"
            value={email}
            onChangeText={setField("email", setEmail)}
            error={fieldErrors.email}
          />
          <View style={{ height: spacing.base }} />
          <TextField
            label="Mobile number"
            placeholder="9876543210"
            keyboardType="phone-pad"
            autoComplete="tel"
            value={phone}
            onChangeText={setField("phone", setPhone)}
            error={fieldErrors.phone}
          />
          <View style={{ height: spacing.base }} />
          <TextField
            label="Password"
            placeholder="At least 8 characters"
            secureTextEntry
            autoComplete="new-password"
            value={password}
            onChangeText={setField("password", setPassword)}
            onSubmitEditing={handleRegister}
            error={fieldErrors.password}
          />

          {error ? (
            <Text variant="bodySmall" color={colors.error} style={styles.error}>
              {error}
            </Text>
          ) : null}

          <View style={{ height: spacing.xl }} />
          <Button label="Create account" onPress={handleRegister} loading={loading} fullWidth size="lg" />

          <View style={styles.footer}>
            <Text variant="body" color={colors.textSecondary}>
              Already have an account?{" "}
            </Text>
            <Link href="/(auth)/login" asChild>
              <Text variant="bodyMedium" color={colors.primary}>
                Log in
              </Text>
            </Link>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { flexGrow: 1, padding: spacing.xl },
  header: { marginBottom: spacing["2xl"] },
  title: { marginTop: spacing.lg },
  error: { marginTop: spacing.md },
  footer: { flexDirection: "row", justifyContent: "center", marginTop: spacing["2xl"], marginBottom: spacing.xl },
});
