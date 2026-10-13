import React, { useMemo, useRef, useState } from "react";
import { FlatList, Modal, Pressable, RefreshControl, StyleSheet, TextInput, useWindowDimensions, View } from "react-native";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { EmptyState } from "@/components/EmptyState";
import { Skeleton } from "@/components/Skeleton";
import { useOrders } from "@/features/orders/useOrders";
import { isActiveOrder, presentOrderStatus } from "@/utils/statusPresentation";
import { formatMoney } from "@/utils/money";
import { CART_BAR_CLEARANCE } from "@/components/CartBar";
import { colors, radius, spacing } from "@/theme";
import { OrderResponse } from "@/types/api";

type Filter = "ALL" | "ACTIVE" | "DELIVERED" | "CANCELLED";

const FILTERS: { key: Filter; label: string; title: string }[] = [
  { key: "ALL", label: "All orders", title: "Previous orders" },
  { key: "ACTIVE", label: "Active", title: "Active orders" },
  { key: "DELIVERED", label: "Delivered", title: "Delivered orders" },
  { key: "CANCELLED", label: "Cancelled", title: "Cancelled orders" },
];

function matchesFilter(order: OrderResponse, filter: Filter): boolean {
  switch (filter) {
    case "ACTIVE":
      return isActiveOrder(order.status);
    case "DELIVERED":
      return order.status === "COMPLETED";
    case "CANCELLED":
      return order.status === "CANCELLED";
    default:
      return true;
  }
}

export default function OrdersScreen() {
  const router = useRouter();
  const { data, isLoading, fetchNextPage, hasNextPage, refetch, isRefetching } = useOrders();
  const [filter, setFilter] = useState<Filter>("ALL");
  const [menuOpen, setMenuOpen] = useState(false);
  // The filter menu is a popover rendered in a Modal (above the list), anchored
  // to the Filter button - inside the list header the order cards drew over it.
  const filterBtnRef = useRef<View>(null);
  const [menuAnchor, setMenuAnchor] = useState<{ top: number; right: number } | null>(null);
  const { width: windowWidth } = useWindowDimensions();

  const toggleMenu = () => {
    if (menuOpen) {
      setMenuOpen(false);
      return;
    }
    filterBtnRef.current?.measureInWindow((x, y, w, h) => {
      setMenuAnchor({ top: y + h + 6, right: Math.max(8, windowWidth - (x + w)) });
      setMenuOpen(true);
    });
  };
  const [query, setQuery] = useState("");

  const orders = useMemo(() => data?.pages.flatMap((p) => p.items) ?? [], [data]);
  const total = data?.pages[0]?.total ?? orders.length;
  const delivered = orders.filter((o) => o.status === "COMPLETED").length;
  const cancelled = orders.filter((o) => o.status === "CANCELLED").length;

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return orders
      .filter((o) => matchesFilter(o, filter))
      .filter((o) => !q || o.order_number.toLowerCase().includes(q));
  }, [orders, filter, query]);

  const current = FILTERS.find((f) => f.key === filter) ?? FILTERS[0];

  const header = (
    <View>
      <View style={styles.hero}>
        <Image
          source={require("../../assets/orders-hero-bag.png")}
          style={styles.heroArt}
          contentFit="contain"
          contentPosition="top right"
        />
        <Text variant="eyebrow" color={colors.accentDark}>
          MY GAWACHA BAZAAR
        </Text>
        <Text variant="displayM" color={colors.primary} style={styles.heroTitle}>
          Your orders
        </Text>
        <Text variant="bodySmall" color={colors.textSecondary} style={styles.heroSub}>
          Track and manage all your grocery orders in one place.
        </Text>
      </View>

      <View style={styles.stats}>
        <Stat icon="file-text" tint={colors.successLight} color={colors.brandGreen} value={total} label="Total Orders" />
        <View style={styles.statDivider} />
        <Stat icon="check" tint={colors.successLight} color={colors.brandGreen} value={delivered} label="Delivered" solid />
        <View style={styles.statDivider} />
        <Stat icon="x" tint={colors.errorLight} color={colors.error} value={cancelled} label="Cancelled" solid />
      </View>

      <View style={styles.titleRow}>
        <Text variant="displayM" color={colors.primary} style={styles.listTitle}>
          {current.title}
        </Text>
        <View>
          <Pressable
            ref={filterBtnRef}
            collapsable={false}
            style={styles.filterBtn}
            onPress={toggleMenu}
            accessibilityRole="button"
            accessibilityLabel="Filter orders"
          >
            <Feather name="filter" size={14} color={colors.primary} />
            <Text variant="bodySmall" color={colors.primary}>
              Filter
            </Text>
            <Feather name={menuOpen ? "chevron-up" : "chevron-down"} size={14} color={colors.primary} />
          </Pressable>
        </View>
      </View>

      <View style={styles.search}>
        <Feather name="search" size={16} color={colors.textSecondary} />
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Search by order ID..."
          placeholderTextColor={colors.textMuted}
          style={styles.searchInput}
          autoCapitalize="characters"
          autoCorrect={false}
          returnKeyType="search"
        />
        {query ? (
          <Pressable onPress={() => setQuery("")} hitSlop={8} accessibilityLabel="Clear search">
            <Feather name="x" size={16} color={colors.textMuted} />
          </Pressable>
        ) : null}
      </View>
    </View>
  );

  return (
    <Screen edges={["top"]}>
      {isLoading ? (
        <View style={styles.loading}>
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} height={70} borderRadius={14} style={{ marginBottom: spacing.md }} />
          ))}
        </View>
      ) : orders.length === 0 ? (
        <EmptyState
          icon="package"
          title="No orders yet"
          message="Your next grocery run starts here."
          actionLabel="Browse products"
          onAction={() => router.replace("/(tabs)")}
        />
      ) : (
        <FlatList
          data={shown}
          keyExtractor={(item) => String(item.id)}
          ListHeaderComponent={header}
          ListEmptyComponent={
            <Text variant="bodySmall" color={colors.textMuted} align="center" style={styles.none}>
              No orders match.
            </Text>
          }
          renderItem={({ item }) => <OrderRow order={item} onPress={() => router.push(`/order/${item.id}`)} />}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          onEndReachedThreshold={0.4}
          onEndReached={() => hasNextPage && fetchNextPage()}
          refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.primary} />}
        />
      )}
      <Modal
        visible={menuOpen}
        transparent
        animationType="fade"
        statusBarTranslucent
        onRequestClose={() => setMenuOpen(false)}
      >
        <Pressable style={styles.menuBackdrop} onPress={() => setMenuOpen(false)} accessibilityLabel="Close filter menu">
          {menuAnchor ? (
            <View style={[styles.menu, { top: menuAnchor.top, right: menuAnchor.right }]}>
              {FILTERS.map((f) => (
                <Pressable
                  key={f.key}
                  style={styles.menuItem}
                  onPress={() => {
                    setFilter(f.key);
                    setMenuOpen(false);
                  }}
                >
                  <Text variant="bodySmall" color={f.key === filter ? colors.brandGreen : colors.textPrimary}>
                    {f.label}
                  </Text>
                  {f.key === filter ? <Feather name="check" size={14} color={colors.brandGreen} /> : null}
                </Pressable>
              ))}
            </View>
          ) : null}
        </Pressable>
      </Modal>
    </Screen>
  );
}

function Stat({
  icon,
  tint,
  color,
  value,
  label,
  solid,
}: {
  icon: keyof typeof Feather.glyphMap;
  tint: string;
  color: string;
  value: number;
  label: string;
  /** Filled circle with a white glyph (delivered/cancelled) vs. tinted circle. */
  solid?: boolean;
}) {
  return (
    <View style={styles.stat}>
      <View style={[styles.statIcon, { backgroundColor: solid ? tint : colors.successLight }]}>
        {solid ? (
          <View style={[styles.statSolid, { backgroundColor: color }]}>
            <Feather name={icon} size={12} color={colors.textInverse} />
          </View>
        ) : (
          <Feather name={icon} size={16} color={color} />
        )}
      </View>
      <View>
        <Text variant="displayM" color={colors.primary} style={styles.statValue}>
          {value}
        </Text>
        <Text variant="caption" color={colors.textSecondary} style={styles.statLabel}>
          {label}
        </Text>
      </View>
    </View>
  );
}

function OrderRow({ order, onPress }: { order: OrderResponse; onPress: () => void }) {
  const presentation = presentOrderStatus(order.status);
  const placedDate = new Date(order.placed_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  return (
    <Pressable style={styles.row} onPress={onPress} accessibilityRole="button">
      <Image source={require("../../assets/order-bag-thumb.png")} style={styles.thumb} contentFit="contain" />
      <View style={styles.rowText}>
        <Text variant="displayM" color={colors.primary} numberOfLines={1} style={styles.orderNo}>
          Order {order.order_number}
        </Text>
        <View style={styles.metaRow}>
          <Feather name="calendar" size={13} color={colors.textSecondary} />
          <Text variant="caption" color={colors.textSecondary} style={styles.meta}>
            {placedDate} · {formatMoney(order.total_amount, order.currency)}
          </Text>
        </View>
      </View>
      <View style={[styles.pill, { backgroundColor: presentation.backgroundColor }]}>
        <View style={[styles.dot, { backgroundColor: presentation.color }]} />
        <Text variant="captionMedium" color={presentation.color} numberOfLines={1} style={styles.pillText}>
          {presentation.label}
        </Text>
      </View>
      <Feather name="chevron-right" size={18} color={colors.textPrimary} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  list: { paddingHorizontal: spacing.base, paddingBottom: CART_BAR_CLEARANCE },
  loading: { padding: spacing.base },
  none: { marginTop: spacing.xl },

  hero: { paddingTop: spacing.lg, paddingBottom: spacing.base, minHeight: 150 },
  heroArt: { position: "absolute", top: -spacing.base, right: -spacing.base, width: 170, height: 131 },
  heroTitle: { fontSize: 28, lineHeight: 34, marginTop: spacing.xs },
  heroSub: { marginTop: spacing.sm, maxWidth: "58%", fontSize: 12.5, lineHeight: 18 },

  stats: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 18,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  stat: { flex: 1, flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingHorizontal: spacing.xs },
  statIcon: { width: 32, height: 32, borderRadius: 16, alignItems: "center", justifyContent: "center" },
  statSolid: { width: 20, height: 20, borderRadius: 10, alignItems: "center", justifyContent: "center" },
  statValue: { fontSize: 22, lineHeight: 26 },
  statLabel: { fontSize: 11, lineHeight: 14 },
  statDivider: { width: 1, height: 34, backgroundColor: colors.divider },

  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.xl,
    zIndex: 2,
  },
  listTitle: { fontSize: 21, lineHeight: 27 },
  filterBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    height: 32,
    paddingHorizontal: 12,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  menuBackdrop: { flex: 1 },
  menu: {
    position: "absolute",
    minWidth: 150,
    backgroundColor: colors.surface,
    borderRadius: 12,
    paddingVertical: spacing.xs,
    shadowColor: "#000",
    shadowOpacity: 0.12,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  menuItem: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: spacing.md,
  },

  search: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    height: 40,
    marginTop: spacing.md,
    marginBottom: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  searchInput: { flex: 1, fontSize: 13, color: colors.textPrimary, paddingVertical: 0 },

  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surface,
    borderRadius: 16,
    paddingVertical: spacing.sm,
    paddingLeft: spacing.sm,
    paddingRight: spacing.md,
    marginBottom: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  thumb: { width: 54, height: 54 },
  rowText: { flex: 1, minWidth: 0 },
  orderNo: { fontSize: 14, lineHeight: 19 },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 4 },
  meta: { fontSize: 12 },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  dot: { width: 7, height: 7, borderRadius: 4 },
  pillText: { fontSize: 11 },
});
