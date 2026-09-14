import React, { useState } from "react";
import { Alert, Pressable, StyleSheet, View } from "react-native";
import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { TextField } from "@/components/TextField";
import { useCancelOrder, useOrder } from "@/features/orders/useOrders";
import { useToastStore } from "@/store/toastStore";
import { toApiError } from "@/api";
import { colors, radius, spacing } from "@/theme";

const REASONS = [
  "Ordered by mistake",
  "Found a better price elsewhere",
  "Delivery is taking too long",
  "Changed my mind",
  "Other",
];

/**
 * Reason -> Confirmation in one screen (brief §33 lists them as separate
 * conceptual steps; combining them here avoids an unnecessary extra
 * navigation for what is a single decision). The backend's own
 * order_state.py remains the sole authority on whether cancellation is
 * legal - this screen only offers the action when the order screen
 * already determined it's eligible, and still surfaces the backend's own
 * rejection honestly if something changed in the meantime (e.g. delivery
 * completed a moment ago).
 */
export default function CancelOrderScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const orderId = Number(id);
  const router = useRouter();
  const { data: order } = useOrder(orderId);
  const cancelOrder = useCancelOrder();
  const showToast = useToastStore((s) => s.show);

  const [selectedReason, setSelectedReason] = useState<string | null>(null);
  const [customReason, setCustomReason] = useState("");

  const finalReason = selectedReason === "Other" ? customReason.trim() : selectedReason;

  const handleConfirm = () => {
    Alert.alert(
      "Cancel this order?",
      "This can't be undone. If you already paid online, your refund will need admin approval before it's processed.",
      [
        { text: "Keep order", style: "cancel" },
        {
          text: "Yes, cancel order",
          style: "destructive",
          onPress: () => {
            cancelOrder.mutate(
              { id: orderId, payload: { reason: finalReason || undefined } },
              {
                onSuccess: () => {
                  showToast("Order cancelled", "success");
                  router.replace(`/order/${orderId}`);
                },
                onError: (err) => showToast(toApiError(err).message, "error"),
              },
            );
          },
        },
      ],
    );
  };

  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: "Cancel order" }} />
      <View style={styles.content}>
        <Text variant="h2">Why are you cancelling?</Text>
        <Text variant="body" color={colors.textSecondary} style={styles.subtitle}>
          Order {order?.order_number}
        </Text>

        <View style={styles.reasons}>
          {REASONS.map((reason) => (
            <Pressable
              key={reason}
              style={[styles.reasonRow, selectedReason === reason && styles.reasonRowActive]}
              onPress={() => setSelectedReason(reason)}
            >
              <View style={[styles.radio, selectedReason === reason && styles.radioActive]}>
                {selectedReason === reason ? <View style={styles.radioDot} /> : null}
              </View>
              <Text variant="body">{reason}</Text>
            </Pressable>
          ))}
        </View>

        {selectedReason === "Other" ? (
          <TextField
            placeholder="Tell us more (optional)"
            value={customReason}
            onChangeText={setCustomReason}
            multiline
            style={styles.customInput}
          />
        ) : null}

        <Button
          label="Cancel order"
          variant="danger"
          onPress={handleConfirm}
          loading={cancelOrder.isPending}
          disabled={!selectedReason}
          fullWidth
          size="lg"
          style={{ marginTop: spacing.xl }}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { flex: 1, padding: spacing.xl },
  subtitle: { marginTop: spacing.xs, marginBottom: spacing.xl },
  reasons: { gap: spacing.sm },
  reasonRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.none,
    borderWidth: 1.5,
    borderColor: colors.border,
  },
  reasonRowActive: { borderColor: colors.primary, backgroundColor: colors.primaryLight },
  radio: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  radioActive: { borderColor: colors.primary },
  radioDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.primary },
  customInput: { marginTop: spacing.base, minHeight: 80, textAlignVertical: "top" },
});
