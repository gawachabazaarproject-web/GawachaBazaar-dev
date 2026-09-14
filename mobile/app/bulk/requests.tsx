import React from "react";
import { FlatList, Pressable, StyleSheet, View } from "react-native";
import { Stack, useRouter } from "expo-router";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { Skeleton } from "@/components/Skeleton";
import { useBulkRequests } from "@/features/bulkOrders/useBulkOrders";
import { presentBulkRequestStatus } from "@/utils/statusPresentation";
import { useWholesaleStore } from "@/store/wholesaleStore";
import { colors, spacing } from "@/theme";
import { BulkOrderRequestResponse } from "@/types/api";

export default function BulkRequestsScreen() {
  const router = useRouter();
  const setMode = useWholesaleStore((s) => s.setMode);
  const { data, isLoading, isFetchingNextPage, fetchNextPage, hasNextPage } = useBulkRequests();

  const requests = data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <Screen edges={["top"]}>
      <Stack.Screen options={{ headerShown: true, title: "Bulk requests" }} />
      <View style={styles.header}>
        <Text variant="eyebrow" color={colors.accentDark}>
          WHOLESALE
        </Text>
        <Text variant="displayM" style={{ marginTop: spacing.xs }}>
          Your requests
        </Text>
      </View>

      {isLoading ? (
        <View style={styles.list}>
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} height={80} borderRadius={0} style={{ marginBottom: spacing.md }} />
          ))}
        </View>
      ) : requests.length === 0 ? (
        <EmptyState
          icon="package"
          title="No bulk requests yet"
          message="Switch to Wholesale mode on Home to request a custom quote."
          actionLabel="Browse wholesale"
          onAction={() => {
            setMode("wholesale");
            router.replace("/(tabs)");
          }}
        />
      ) : (
        <FlatList
          data={requests}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <RequestRow request={item} onPress={() => router.push({ pathname: "/bulk/[id]", params: { id: String(item.id) } })} />
          )}
          onEndReachedThreshold={0.4}
          onEndReached={() => hasNextPage && fetchNextPage()}
          ListFooterComponent={isFetchingNextPage ? <Skeleton height={80} borderRadius={0} /> : null}
        />
      )}
    </Screen>
  );
}

function RequestRow({ request, onPress }: { request: BulkOrderRequestResponse; onPress: () => void }) {
  const presentation = presentBulkRequestStatus(request.status);
  const itemCount = request.items.length;
  const placedDate = new Date(request.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" });

  return (
    <Pressable style={styles.row} onPress={onPress}>
      <View style={{ flex: 1 }}>
        <Text variant="bodyMedium">
          {itemCount} {itemCount === 1 ? "item" : "items"} requested
        </Text>
        <Text variant="bodySmall" color={colors.textSecondary} style={{ marginTop: 2 }}>
          {placedDate}
        </Text>
        <View style={{ marginTop: spacing.sm }}>
          <StatusBadge presentation={presentation} />
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: spacing.base, paddingTop: spacing.md, paddingBottom: spacing.sm },
  list: { padding: spacing.base },
  row: {
    paddingVertical: spacing.base,
    borderBottomWidth: 1,
    borderColor: colors.divider,
  },
});
