import React from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet } from "react-native";
import { Stack, useRouter } from "expo-router";
import { Screen } from "@/components/Screen";
import { AddressForm } from "@/features/address/AddressForm";
import { useCreateAddress } from "@/features/address/useAddresses";
import { useToastStore } from "@/store/toastStore";
import { toApiError } from "@/api";
import { spacing } from "@/theme";

export default function AddAddressScreen() {
  const router = useRouter();
  const createAddress = useCreateAddress();
  const showToast = useToastStore((s) => s.show);

  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: "Add address" }} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.select({ ios: "padding", android: undefined })}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <AddressForm
            submitLabel="Save address"
            loading={createAddress.isPending}
            onSubmit={(payload) => {
              createAddress.mutate(payload, {
                onSuccess: () => {
                  showToast("Address saved", "success");
                  router.back();
                },
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
});
