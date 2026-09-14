import React from "react";
import { Pressable, RefreshControl, SectionList, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { Skeleton } from "@/components/Skeleton";
import { useOrders } from "@/features/orders/useOrders";
import { isActiveOrder, presentOrderStatus } from "@/utils/statusPresentation";
import { formatMoney } from "@/utils/money";
import { colors, radius, spacing } from "@/theme";
import { OrderResponse } from "@/types/api";

export default function OrdersScreen() {
  const router = useRouter();
  const { data, isLoading, isFetchingNextPage, fetchNextPage, hasNextPage, refetch, isRefetching } = useOrders();

  const orders = data?.pages.flatMap((p) => p.items) ?? [];
  const sections = [
    { title: "Active orders", data: orders.filter((o) => isActiveOrder(o.status)) },
    { title: "Previous orders", data: orders.filter((o) => !isActiveOrder(o.status)) },
  ].filter((s) => s.data.length > 0);

  return (
    <Screen edges={["top"]}>
      <View style={styles.header}>
        <Text variant="h1">Your orders</Text>
      </View>

      {isLoading ? (
        <View style={styles.list}>
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} height={90} borderRadius={radius.lg} style={{ marginBottom: spacing.md }} />
          ))}
        </View>
      ) : sections.length === 0 ? (
        <EmptyState
          icon="package"
          title="No orders yet"
          message="Your next grocery run starts here."
          actionLabel="Browse products"
          onAction={() => router.replace("/(tabs)")}
        />
      ) : (
        <SectionList
          sections={sections}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={styles.list}
          renderSectionHeader={({ section }) => (
            <Text variant="h3" style={styles.sectionTitle}>
              {section.title}
            </Text>
          )}
          renderItem={({ item }) => <OrderRow order={item} onPress={() => router.push(`/order/${item.id}`)} />}
          onEndReachedThreshold={0.4}
          onEndReached={() => hasNextPage && fetchNextPage()}
          refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.primary} />}
        />
      )}
    </Screen>
  );
}

function OrderRow({ order, onPress }: { order: OrderResponse; onPress: () => void }) {
  const presentation = presentOrderStatus(order.status);
  const placedDate = new Date(order.placed_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  return (
    <Pressable style={styles.row} onPress={onPress}>
      <View style={styles.rowTop}>
        <Text variant="bodyMedium">Order {order.order_number}</Text>
        <StatusBadge presentation={presentation} />
      </View>
      <View style={styles.rowBottom}>
        <Text variant="bodySmall" color={colors.textSecondary}>
          {placedDate}
        </Text>
        <Text variant="bodyMedium">{formatMoney(order.total_amount, order.currency)}</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: spacing.base, paddingTop: spacing.md, paddingBottom: spacing.sm },
  list: { padding: spacing.base },
  sectionTitle: { marginTop: spacing.md, marginBottom: spacing.sm },
  row: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.base,
    marginBottom: spacing.md,
  },
  rowTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.sm },
  rowBottom: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
});
