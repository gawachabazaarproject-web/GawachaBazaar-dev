import React from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from "react-native";
import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { Screen } from "@/components/Screen";
import { AddressForm } from "@/features/address/AddressForm";
import { useAddress, useUpdateAddress } from "@/features/address/useAddresses";
import { useToastStore } from "@/store/toastStore";
import { toApiError } from "@/api";
import { colors, spacing } from "@/theme";

export default function EditAddressScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const addressId = Number(id);
  const router = useRouter();
  const { data: address, isLoading } = useAddress(addressId);
  const updateAddress = useUpdateAddress();
  const showToast = useToastStore((s) => s.show);

  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: "Edit address" }} />
      {isLoading || !address ? (
        <View style={styles.loading}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : (
        <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.select({ ios: "padding", android: undefined })}>
          <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
            <AddressForm
              initial={address}
              submitLabel="Save changes"
              loading={updateAddress.isPending}
              onSubmit={(payload) => {
                updateAddress.mutate(
                  { id: addressId, payload },
                  {
                    onSuccess: () => {
                      showToast("Address updated", "success");
                      router.back();
                    },
                    onError: (err) => showToast(toApiError(err).message, "error"),
                  },
                );
              }}
            />
          </ScrollView>
        </KeyboardAvoidingView>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { flexGrow: 1, padding: spacing.xl },
  loading: { flex: 1, alignItems: "center", justifyContent: "center" },
});
