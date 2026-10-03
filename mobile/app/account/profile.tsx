import React from "react";
import { StyleSheet, View } from "react-native";
import { Stack, useRouter } from "expo-router";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { useAuthStore } from "@/store/authStore";
import { colors, spacing } from "@/theme";

/**
 * Read-only for this MVP - the backend has no PATCH /auth/me endpoint yet
 * (Phase 19 finding, classified P2/backlog). Shown here rather than
 * hidden entirely so the customer can at least confirm their details.
 */
export default function ProfileScreen() {
  const user = useAuthStore((s) => s.user);
  const router = useRouter();

  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: "Profile" }} />
      <View style={styles.content}>
        <Field label="Full name" value={user?.name ?? "-"} />
        <Field label="Email" value={user?.email ?? "-"} />
        <Field label="Mobile number" value={user?.phone ?? "-"} />
        {user && !user.phone ? (
          <View style={styles.addPhone}>
            <Button label="Add mobile number" variant="outline" onPress={() => router.push("/account/add-phone")} fullWidth />
          </View>
        ) : null}
        <Text variant="caption" color={colors.textMuted} style={styles.note}>
          Need to update your details? Contact support.
        </Text>
      </View>
    </Screen>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.field}>
      <Text variant="caption" color={colors.textSecondary}>
        {label}
      </Text>
      <Text variant="bodyLarge" style={{ marginTop: spacing.xs }}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.xl },
  field: {
    paddingVertical: spacing.base,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  note: { marginTop: spacing.xl },
  addPhone: { marginTop: spacing.lg },
});
