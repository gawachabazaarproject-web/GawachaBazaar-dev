import React from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { Stack, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { TextField } from "@/components/TextField";
import { EmptyState } from "@/components/EmptyState";
import { useAddresses } from "@/features/address/useAddresses";
import { useCreateBulkRequest } from "@/features/bulkOrders/useBulkOrders";
import { useWholesaleStore } from "@/store/wholesaleStore";
import { useToastStore } from "@/store/toastStore";
import { toApiError } from "@/api";
import { colors, radius, spacing } from "@/theme";

/**
 * Builds and submits a BulkOrderRequest from the current draft (see
 * wholesaleStore.ts). This is a REQUEST, not a purchase - no price is
 * shown or computed here; ops prices it separately as a Quote the
 * customer can review and accept afterward (see bulk_order.py).
 */
export default function BulkReviewScreen() {
  const router = useRouter();
  const { data: addresses } = useAddresses();
  const createRequest = useCreateBulkRequest();
  const showToast = useToastStore((s) => s.show);

  const draftItems = useWholesaleStore((s) => s.draftItems);
  const removeItem = useWholesaleStore((s) => s.removeItem);
  const notes = useWholesaleStore((s) => s.notes);
  const setNotes = useWholesaleStore((s) => s.setNotes);
  const addressId = useWholesaleStore((s) => s.addressId);
  const setAddressId = useWholesaleStore((s) => s.setAddressId);
  const clearDraft = useWholesaleStore((s) => s.clearDraft);

  const handleSubmit = () => {
    createRequest.mutate(
      {
        address_id: addressId,
        customer_notes: notes.trim() || null,
        items: draftItems.map((item) => ({
          product_id: item.productId,
          requested_quantity: item.quantity,
          unit: item.unit,
        })),
      },
      {
        onSuccess: (request) => {
          clearDraft();
          router.replace({ pathname: "/bulk/success", params: { id: String(request.id) } });
        },
        onError: (err) => showToast(toApiError(err).message, "error"),
      },
    );
  };

  return (
    <Screen edges={["top", "bottom"]}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={8} accessibilityRole="button" accessibilityLabel="Close">
          <Feather name="x" size={20} color={colors.textPrimary} />
        </Pressable>
        <Text variant="h3">Bulk Request</Text>
        <View style={{ width: 20 }} />
      </View>

      {draftItems.length === 0 ? (
        <EmptyState
          icon="package"
          title="Your request is empty"
          message="Switch to Wholesale mode and add items to build a bulk order request."
          actionLabel="Browse wholesale"
          onAction={() => {
            useWholesaleStore.getState().setMode("wholesale");
            router.replace("/(tabs)");
          }}
        />
      ) : (
        <>
          <ScrollView contentContainerStyle={styles.content}>
            <Text variant="eyebrow" color={colors.accentDark}>
              WHOLESALE
            </Text>
            <Text variant="displayM" style={styles.title}>
              Review your request
            </Text>
            <Text variant="body" color={colors.textSecondary} style={styles.subtitle}>
              This sends a request for pricing - our team will quote you directly, nothing is
              charged yet.
            </Text>

            <View style={styles.list}>
              {draftItems.map((item) => (
                <View key={item.productId} style={styles.itemRow}>
                  <Image
                    source={item.imageUrl ?? undefined}
                    style={styles.itemImage}
                    contentFit="cover"
                    placeholder={{ blurhash: "L4C~D%~q00~q~q00%M-;9F%M-;-;" }}
                  />
                  <View style={{ flex: 1 }}>
                    <Text variant="bodyMedium" numberOfLines={1}>
                      {item.productName}
                    </Text>
                    <Text variant="caption" color={colors.textSecondary}>
                      {item.quantity} {item.unit}
                    </Text>
                  </View>
                  <Pressable onPress={() => removeItem(item.productId)} hitSlop={8} accessibilityRole="button" accessibilityLabel="Remove item">
                    <Feather name="trash-2" size={16} color={colors.error} />
                  </Pressable>
                </View>
              ))}
            </View>

            <Text variant="eyebrow" color={colors.accentDark} style={styles.sectionLabel}>
              DELIVERY ADDRESS (OPTIONAL)
            </Text>
            {(addresses ?? []).length === 0 ? (
              <Pressable onPress={() => router.push("/address/add")} style={styles.addAddressLink}>
                <Feather name="plus" size={14} color={colors.primary} />
                <Text variant="bodyMedium" color={colors.primary} style={{ marginLeft: spacing.xs }}>
                  Add an address
                </Text>
              </Pressable>
            ) : (
              (addresses ?? []).map((address) => {
                const selected = addressId === address.id;
                return (
                  <Pressable
                    key={address.id}
                    style={styles.addressOption}
                    onPress={() => setAddressId(selected ? null : address.id)}
                  >
                    <View style={[styles.radio, selected && styles.radioActive]}>
                      {selected ? <View style={styles.radioDot} /> : null}
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text variant="bodyMedium">{address.label}</Text>
                      <Text variant="bodySmall" color={colors.textSecondary}>
                        {address.address_line_1}, {address.city}, {address.state} {address.postal_code}
                      </Text>
                    </View>
                  </Pressable>
                );
              })
            )}

            <Text variant="eyebrow" color={colors.accentDark} style={styles.sectionLabel}>
              NOTES (OPTIONAL)
            </Text>
            <TextField
              value={notes}
              onChangeText={setNotes}
              placeholder="Anything our team should know - delivery window, packaging, etc."
              multiline
              style={styles.notesInput}
            />
          </ScrollView>

          <View style={styles.footer}>
            <Button
              label="Submit request"
              onPress={handleSubmit}
              loading={createRequest.isPending}
              fullWidth
              size="lg"
            />
          </View>
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderColor: colors.divider,
  },
  content: { padding: spacing.base, paddingBottom: spacing["3xl"] },
  title: { marginTop: spacing.xs },
  subtitle: { marginTop: spacing.sm, marginBottom: spacing.xl },
  list: { gap: 0 },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderColor: colors.divider,
  },
  itemImage: { width: 56, height: 56, borderRadius: radius.none, backgroundColor: colors.background },
  sectionLabel: { marginTop: spacing.xl, marginBottom: spacing.md },
  addAddressLink: { flexDirection: "row", alignItems: "center" },
  addressOption: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm, marginBottom: spacing.md },
  radio: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
  },
  radioActive: { borderColor: colors.primary },
  radioDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.primary },
  notesInput: { minHeight: 90, textAlignVertical: "top" },
  footer: { padding: spacing.base, borderTopWidth: 1, borderColor: colors.divider },
});
