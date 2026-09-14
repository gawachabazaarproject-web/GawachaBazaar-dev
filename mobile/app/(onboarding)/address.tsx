import React from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from "react-native";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { AddressForm } from "@/features/address/AddressForm";
import { useCreateAddress } from "@/features/address/useAddresses";
import { useToastStore } from "@/store/toastStore";
import { toApiError } from "@/api";
import { colors, spacing } from "@/theme";

/** First-time flow (brief §20): shown once, right after authentication,
 * when the customer has zero saved addresses. AppGate redirects away the
 * moment one exists. */
export default function AddressOnboardingScreen() {
  const createAddress = useCreateAddress();
  const showToast = useToastStore((s) => s.show);

  return (
    <Screen>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.select({ ios: "padding", android: undefined })}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.header}>
            <Text variant="h1">Where should we deliver?</Text>
            <Text variant="body" color={colors.textSecondary} style={styles.subtitle}>
              Add your delivery address to start shopping. You can add more addresses anytime.
            </Text>
          </View>

          <AddressForm
            submitLabel="Save and continue"
            loading={createAddress.isPending}
            allowDefaultToggle={false}
            onSubmit={(payload) => {
              createAddress.mutate(payload, {
                onError: (err) => showToast(toApiError(err).message, "error"),
              });
            }}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { flexGrow: 1, padding: spacing.xl },
  header: { marginBottom: spacing["2xl"] },
  subtitle: { marginTop: spacing.sm },
});
