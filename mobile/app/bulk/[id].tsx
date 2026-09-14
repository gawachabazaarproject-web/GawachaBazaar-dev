import React from "react";
import { ActivityIndicator, Alert, ScrollView, StyleSheet, View } from "react-native";
import { Stack, useLocalSearchParams } from "expo-router";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { StatusBadge } from "@/components/StatusBadge";
import {
  useAcceptBulkQuote,
  useBulkQuote,
  useBulkRequest,
  useCancelBulkRequest,
} from "@/features/bulkOrders/useBulkOrders";
import { presentBulkRequestStatus, isBulkRequestCancellable } from "@/utils/statusPresentation";
import { formatMoney } from "@/utils/money";
import { useToastStore } from "@/store/toastStore";
import { toApiError } from "@/api";
import { colors, radius, spacing } from "@/theme";

export default function BulkRequestDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const requestId = Number(id);
  const showToast = useToastStore((s) => s.show);

  const { data: request, isLoading } = useBulkRequest(requestId);
  const { data: quote } = useBulkQuote(requestId);
  const acceptQuote = useAcceptBulkQuote();
  const cancelRequest = useCancelBulkRequest();

  if (isLoading || !request) {
    return (
      <Screen>
        <Stack.Screen options={{ headerShown: true, title: "Bulk request" }} />
        <View style={styles.centered}>
          <ActivityIndicator color={colors.primary} />
        </View>
      </Screen>
    );
  }

  const presentation = presentBulkRequestStatus(request.status);
  const sentVersion = quote?.versions.find((v) => v.status === "SENT");
  const cancellable = isBulkRequestCancellable(request.status);

  const handleAccept = () => {
    acceptQuote.mutate(requestId, {
      onError: (err) => showToast(toApiError(err).message, "error"),
    });
  };

  const handleCancel = () => {
    Alert.alert("Cancel this request?", "This can't be undone.", [
      { text: "Keep request", style: "cancel" },
      {
        text: "Yes, cancel",
        style: "destructive",
        onPress: () =>
          cancelRequest.mutate(requestId, {
            onError: (err) => showToast(toApiError(err).message, "error"),
          }),
      },
    ]);
  };

  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: `Request #${request.id}` }} />
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.headerRow}>
          <View>
            <Text variant="h2">Request #{request.id}</Text>
            <Text variant="bodySmall" color={colors.textSecondary}>
              {new Date(request.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}
            </Text>
          </View>
          <StatusBadge presentation={presentation} />
        </View>

        <SectionCard title={`Items (${request.items.length})`}>
          {request.items.map((item) => (
            <View key={item.id} style={styles.itemRow}>
              <View style={{ flex: 1 }}>
                <Text variant="body" numberOfLines={1}>
                  {item.product_name ?? item.custom_item_name}
                </Text>
                {item.customer_notes ? (
                  <Text variant="caption" color={colors.textSecondary}>
                    {item.customer_notes}
                  </Text>
                ) : null}
              </View>
              <Text variant="bodyMedium">
                {item.requested_quantity} {item.unit}
              </Text>
            </View>
          ))}
        </SectionCard>

        {request.address ? (
          <SectionCard title="Delivery address">
            <Text variant="body">
              {request.address.address_line_1}
              {request.address.address_line_2 ? `, ${request.address.address_line_2}` : ""}
            </Text>
            <Text variant="body" color={colors.textSecondary}>
              {request.address.city}, {request.address.state} {request.address.postal_code}
            </Text>
          </SectionCard>
        ) : null}

        {request.customer_notes ? (
          <SectionCard title="Your notes">
            <Text variant="body" color={colors.textSecondary}>
              {request.customer_notes}
            </Text>
          </SectionCard>
        ) : null}

        {sentVersion ? (
          <SectionCard title="Quote">
            {sentVersion.items.map((qi) => (
              <View key={qi.id} style={styles.itemRow}>
                <View style={{ flex: 1 }}>
                  <Text variant="body" numberOfLines={1}>
                    {qi.variant_name}
                  </Text>
                  <Text variant="caption" color={colors.textSecondary}>
                    {qi.quantity} × {formatMoney(qi.unit_price, sentVersion.currency)}
                  </Text>
                </View>
                <Text variant="bodyMedium">{formatMoney(qi.total_price, sentVersion.currency)}</Text>
              </View>
            ))}
            <View style={styles.divider} />
            <View style={styles.itemRow}>
              <Text variant="h3">Total</Text>
              <Text variant="h3">
                {formatMoney(
                  sentVersion.items.reduce((sum, qi) => sum + Number.parseFloat(qi.total_price), 0),
                  sentVersion.currency,
                )}
              </Text>
            </View>
            {sentVersion.valid_until ? (
              <Text variant="caption" color={colors.textSecondary} style={{ marginTop: spacing.sm }}>
                Valid until {new Date(sentVersion.valid_until).toLocaleDateString("en-IN", { day: "numeric", month: "long" })}
              </Text>
            ) : null}
            {sentVersion.admin_notes ? (
              <Text variant="caption" color={colors.textSecondary} style={{ marginTop: spacing.xs }}>
                {sentVersion.admin_notes}
              </Text>
            ) : null}

            {request.status === "QUOTED" ? (
              <Button
                label="Accept quote"
                onPress={handleAccept}
                loading={acceptQuote.isPending}
                fullWidth
                style={{ marginTop: spacing.lg }}
              />
            ) : null}
          </SectionCard>
        ) : request.status === "REQUESTED" || request.status === "UNDER_REVIEW" ? (
          <SectionCard title="Quote">
            <Text variant="body" color={colors.textSecondary}>
              Our team is reviewing your request. You&apos;ll see pricing here once it&apos;s
              ready.
            </Text>
          </SectionCard>
        ) : null}

        {request.status === "CUSTOMER_ACCEPTED" ? (
          <Text variant="bodySmall" color={colors.success} align="center" style={{ marginTop: spacing.base }}>
            Quote accepted - we&apos;ll confirm your order shortly.
          </Text>
        ) : null}
        {request.status === "CONVERTED_TO_ORDER" ? (
          <Text variant="bodySmall" color={colors.success} align="center" style={{ marginTop: spacing.base }}>
            Converted to an order - check your Orders tab for tracking.
          </Text>
        ) : null}

        {cancellable ? (
          <Button
            label="Cancel request"
            variant="outline"
            onPress={handleCancel}
            loading={cancelRequest.isPending}
            style={{ marginTop: spacing.lg }}
          />
        ) : null}
      </ScrollView>
    </Screen>
  );
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.card}>
      <Text variant="h3" style={styles.cardTitle}>
        {title}
      </Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.base, paddingBottom: spacing["3xl"] },
  centered: { flex: 1, alignItems: "center", justifyContent: "center" },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: spacing.lg },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.divider,
    borderRadius: radius.none,
    padding: spacing.base,
    marginBottom: spacing.base,
  },
  cardTitle: { marginBottom: spacing.md },
  itemRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: spacing.xs, marginBottom: spacing.xs },
  divider: { height: 1, backgroundColor: colors.divider, marginVertical: spacing.sm },
});
