import React from "react";
import { Pressable, RefreshControl, SectionList, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { Skeleton } from "@/components/Skeleton";
import { useOrders } from "@/features/orders/useOrders";
import { isActiveOrder, presentOrderStatus } from "@/utils/statusPresentation";
import { formatMoney } from "@/utils/money";
import { colors, spacing } from "@/theme";
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
        <Text variant="eyebrow" color={colors.accentDark}>
          MY GAWACHA BAZAAR
        </Text>
        <Text variant="displayM" style={{ marginTop: spacing.xs }}>
          Your orders
        </Text>
      </View>

      {isLoading ? (
        <View style={styles.list}>
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} height={80} borderRadius={0} style={{ marginBottom: spacing.md }} />
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
            <Text variant="eyebrow" color={colors.textMuted} style={styles.sectionTitle}>
              {section.title.toUpperCase()}
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
      <View style={{ flex: 1 }}>
        <Text variant="bodyMedium">Order {order.order_number}</Text>
        <Text variant="bodySmall" color={colors.textSecondary} style={{ marginTop: 2 }}>
          {placedDate} &middot; {formatMoney(order.total_amount, order.currency)}
        </Text>
        <View style={{ marginTop: spacing.sm }}>
          <StatusBadge presentation={presentation} />
        </View>
      </View>
      <Feather name="arrow-up-right" size={16} color={colors.textMuted} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: spacing.base, paddingTop: spacing.lg, paddingBottom: spacing.sm },
  list: { padding: spacing.base },
  sectionTitle: { marginTop: spacing.lg, marginBottom: spacing.sm },
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingVertical: spacing.base,
    borderBottomWidth: 1,
    borderColor: colors.divider,
  },
});
