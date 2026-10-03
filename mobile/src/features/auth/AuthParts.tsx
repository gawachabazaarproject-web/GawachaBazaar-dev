import React from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { Wordmark } from "@/components/Wordmark";
import { colors, radius, spacing } from "@/theme";

/** Shared shell for every auth screen: keyboard-safe, scrollable, centered. */
export function AuthScreen({
  title,
  subtitle,
  showWordmark = false,
  children,
}: {
  title?: string;
  subtitle?: string;
  showWordmark?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Screen>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.select({ ios: "padding", android: undefined })}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.inner}>
            {showWordmark || title ? (
              <View style={styles.header}>
                {showWordmark ? <Wordmark /> : null}
                {title ? (
                  <Text variant="h1" align="center" style={showWordmark ? styles.titleAfterMark : undefined}>
                    {title}
                  </Text>
                ) : null}
                {subtitle ? (
                  <Text variant="body" color={colors.textSecondary} align="center" style={styles.subtitle}>
                    {subtitle}
                  </Text>
                ) : null}
              </View>
            ) : null}
            {children}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  );
}

/** ──────── OR ──────── */
export function OrDivider() {
  return (
    <View style={styles.divider} accessibilityRole="none">
      <View style={styles.line} />
      <Text variant="caption" color={colors.textMuted} style={styles.or}>
        OR
      </Text>
      <View style={styles.line} />
    </View>
  );
}

export function GoogleButton({ onPress, loading, disabled }: { onPress: () => void; loading?: boolean; disabled?: boolean }) {
  return (
    <Button
      label="Continue with Google"
      variant="outline"
      size="lg"
      fullWidth
      onPress={onPress}
      loading={loading}
      disabled={disabled}
      icon={<Ionicons name="logo-google" size={18} color={colors.textPrimary} />}
    />
  );
}

export function PhoneButton({ onPress, disabled }: { onPress: () => void; disabled?: boolean }) {
  return (
    <Button
      label="Continue with Phone"
      variant="outline"
      size="lg"
      fullWidth
      onPress={onPress}
      disabled={disabled}
      icon={<Ionicons name="phone-portrait-outline" size={18} color={colors.textPrimary} />}
    />
  );
}

export function ErrorBanner({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return (
    <View style={[styles.banner, styles.bannerError]} accessibilityRole="alert">
      <Ionicons name="alert-circle-outline" size={18} color={colors.error} />
      <Text variant="bodySmall" color={colors.error} style={styles.bannerText}>
        {message}
      </Text>
    </View>
  );
}

export function NoticeBanner({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return (
    <View style={[styles.banner, styles.bannerInfo]}>
      <Ionicons name="checkmark-circle-outline" size={18} color={colors.success} />
      <Text variant="bodySmall" color={colors.textPrimary} style={styles.bannerText}>
        {message}
      </Text>
    </View>
  );
}

export const authStyles = StyleSheet.create({
  gap: { height: spacing.base },
  gapLg: { height: spacing.xl },
  footer: { flexDirection: "row", justifyContent: "center", flexWrap: "wrap", marginTop: spacing["2xl"] },
  linkRow: { alignItems: "flex-end", marginTop: spacing.sm },
});

const styles = StyleSheet.create({
  content: { flexGrow: 1, padding: spacing.xl, justifyContent: "center" },
  inner: { width: "100%", maxWidth: 440, alignSelf: "center" },
  header: { marginBottom: spacing["2xl"], alignItems: "center" },
  titleAfterMark: { marginTop: spacing.lg },
  subtitle: { marginTop: spacing.sm },
  divider: { flexDirection: "row", alignItems: "center", marginVertical: spacing.xl },
  line: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: colors.borderStrong },
  or: { marginHorizontal: spacing.md, letterSpacing: 1.5 },
  banner: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.md,
    marginTop: spacing.base,
  },
  bannerError: { backgroundColor: colors.errorLight },
  bannerInfo: { backgroundColor: colors.successLight },
  bannerText: { flex: 1 },
});
