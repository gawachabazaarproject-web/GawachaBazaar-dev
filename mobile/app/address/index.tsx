import React from "react";
import { Alert, FlatList, Pressable, StyleSheet, View } from "react-native";
import { useRouter, Stack } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { useAddresses, useDeleteAddress } from "@/features/address/useAddresses";
import { useToastStore } from "@/store/toastStore";
import { toApiError } from "@/api";
import { colors, radius, spacing } from "@/theme";
import { AddressResponse } from "@/types/api";

export default function AddressListScreen() {
  const router = useRouter();
  const { data: addresses, isLoading } = useAddresses();
  const deleteAddress = useDeleteAddress();
  const showToast = useToastStore((s) => s.show);

  const confirmDelete = (address: AddressResponse) => {
    Alert.alert("Delete address", `Remove "${address.label}" from your address book?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: () =>
          deleteAddress.mutate(address.id, {
            onError: (err) => showToast(toApiError(err).message, "error"),
          }),
      },
    ]);
  };

  return (
    <Screen edges={["top", "bottom"]}>
      <Stack.Screen options={{ headerShown: true, title: "Saved addresses" }} />
      {!isLoading && (addresses?.length ?? 0) === 0 ? (
        <EmptyState
          icon="map-pin"
          title="No addresses yet"
          message="Add a delivery address to start shopping."
          actionLabel="Add address"
          onAction={() => router.push("/address/add")}
        />
      ) : (
        <FlatList
          data={addresses ?? []}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <Pressable style={styles.card} onPress={() => router.push(`/address/edit/${item.id}`)}>
              <View style={styles.cardHeader}>
                <Text variant="h3">{item.label}</Text>
                {item.is_default ? (
                  <View style={styles.defaultBadge}>
                    <Text variant="captionMedium" color={colors.primary}>
                      DEFAULT
                    </Text>
                  </View>
                ) : null}
              </View>
              <Text variant="body" color={colors.textSecondary} style={styles.addressText}>
                {item.address_line_1}
                {item.address_line_2 ? `, ${item.address_line_2}` : ""}, {item.city}, {item.state}{" "}
                {item.postal_code}
              </Text>
              <View style={styles.actions}>
                <Pressable style={styles.actionButton} onPress={() => router.push(`/address/edit/${item.id}`)}>
                  <Feather name="edit-2" size={14} color={colors.textSecondary} />
                  <Text variant="bodySmall" color={colors.textSecondary}>
                    Edit
                  </Text>
                </Pressable>
                <Pressable style={styles.actionButton} onPress={() => confirmDelete(item)}>
                  <Feather name="trash-2" size={14} color={colors.error} />
                  <Text variant="bodySmall" color={colors.error}>
                    Delete
                  </Text>
                </Pressable>
              </View>
            </Pressable>
          )}
          ListFooterComponent={
            <Button label="Add new address" variant="outline" onPress={() => router.push("/address/add")} style={{ marginTop: spacing.base }} />
          }
        />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.base },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.base,
    marginBottom: spacing.base,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  defaultBadge: { backgroundColor: colors.primaryLight, paddingHorizontal: spacing.sm, paddingVertical: 2, borderRadius: radius.pill },
  addressText: { marginTop: spacing.xs },
  actions: { flexDirection: "row", gap: spacing.lg, marginTop: spacing.md },
  actionButton: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
});
