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

export default function RegisterScreen() {
  const router = useRouter();
  const register = useAuthStore((s) => s.register);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleRegister = async () => {
    setError(null);
    if (!name.trim() || !email.trim() || !phone.trim() || !password) {
      setError("Please fill in every field to create your account.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
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

          <TextField label="Full name" placeholder="Priya Sharma" value={name} onChangeText={setName} autoComplete="name" />
          <View style={{ height: spacing.base }} />
          <TextField
            label="Email"
            placeholder="you@example.com"
            autoCapitalize="none"
            keyboardType="email-address"
            autoComplete="email"
            value={email}
            onChangeText={setEmail}
          />
          <View style={{ height: spacing.base }} />
          <TextField
            label="Mobile number"
            placeholder="9876543210"
            keyboardType="phone-pad"
            autoComplete="tel"
            value={phone}
            onChangeText={setPhone}
          />
          <View style={{ height: spacing.base }} />
          <TextField
            label="Password"
            placeholder="At least 8 characters"
            secureTextEntry
            autoComplete="new-password"
            value={password}
            onChangeText={setPassword}
            onSubmitEditing={handleRegister}
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
