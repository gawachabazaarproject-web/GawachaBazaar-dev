import React, { useState } from "react";
import { ActivityIndicator, Alert, FlatList, Pressable, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { partnerApi, toApiError, type Assignment } from "@/api";
import { useAuthStore } from "@/store/authStore";
import { useToastStore } from "@/store/toastStore";
import { colors, radius, spacing } from "@/theme";

type Tab = "active" | "history" | "earnings";
const rupees = (v: string) => `Rs ${Number(v).toFixed(0)}`;

/** Delivery-partner home: availability, today's numbers, gig list, history,
 * earnings. Everything (statuses, COD amounts, earnings) comes from the server. */
export default function PartnerHome() {
  const router = useRouter();
  const qc = useQueryClient();
  const show = useToastStore((s) => s.show);
  const logout = useAuthStore((s) => s.logout);
  const [tab, setTab] = useState<Tab>("active");

  const me = useQuery({ queryKey: ["partner", "me"], queryFn: partnerApi.me, refetchInterval: 30_000 });
  const list = useQuery({
    queryKey: ["partner", "list", tab],
    queryFn: () => partnerApi.list(tab === "history" ? "history" : "active"),
    enabled: tab !== "earnings",
    refetchInterval: tab === "active" ? 15_000 : false,
  });
  const earnings = useQuery({ queryKey: ["partner", "earnings"], queryFn: partnerApi.earnings, enabled: tab === "earnings" });

  const toggle = useMutation({
    mutationFn: (next: "OFFLINE" | "AVAILABLE") => partnerApi.setAvailability(next),
    onSuccess: (d) => qc.setQueryData(["partner", "me"], d),
    onError: (e) => show(toApiError(e).message, "error"),
  });

  const online = me.data?.availability !== "OFFLINE";
  const confirmLogout = () =>
    Alert.alert("Log out", "Are you sure?", [
      { text: "Cancel", style: "cancel" },
      { text: "Log out", style: "destructive", onPress: () => logout() },
    ]);

  const renderJob = ({ item }: { item: Assignment }) => (
    <Pressable style={styles.card} onPress={() => router.push(`/partner/${item.id}` as never)} accessibilityRole="button">
      <View style={{ flex: 1 }}>
        <Text variant="bodyMedium">#{item.order_number}</Text>
        <Text variant="bodySmall" color={colors.textSecondary} numberOfLines={2}>
          {item.address ? `${item.address.address_line_1}, ${item.address.city}` : item.status}
        </Text>
        {item.cod_status === "COD_PENDING" ? (
          <Text variant="bodySmall" color={colors.accentDark}>Collect {rupees(item.cod_expected_amount)} cash</Text>
        ) : null}
      </View>
      <View style={styles.pill}>
        <Text variant="bodySmall" color={colors.primary}>{item.status.replace(/_/g, " ")}</Text>
      </View>
    </Pressable>
  );

  return (
    <Screen>
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text variant="eyebrow" color={colors.accentDark}>DELIVERY PARTNER</Text>
          <Text variant="h2">{me.data?.name ?? "Hello"}</Text>
        </View>
        <Pressable onPress={confirmLogout} accessibilityRole="button" accessibilityLabel="Log out">
          <Text variant="bodyMedium" color={colors.primary}>Log out</Text>
        </Pressable>
      </View>

      {me.isError ? (
        <Pressable onPress={() => me.refetch()}>
          <Text color={colors.error} style={styles.pad}>{toApiError(me.error).message} Tap to retry.</Text>
        </Pressable>
      ) : (
        <View style={styles.pad}>
          <View style={styles.statsRow}>
            <Stat label="Active" value={String(me.data?.active_assignments ?? "-")} />
            <Stat label="Done today" value={String(me.data?.delivered_today ?? "-")} />
            <Stat label="Earned today" value={me.data ? rupees(me.data.earned_today) : "-"} />
          </View>
          <Button
            label={me.data?.availability === "ON_DELIVERY" ? "On delivery" : online ? "Online - tap to go offline" : "Offline - tap to go online"}
            variant={online ? "secondary" : "primary"}
            loading={toggle.isPending}
            disabled={me.data?.availability === "ON_DELIVERY" || me.data?.status !== "ACTIVE"}
            onPress={() => toggle.mutate(online ? "OFFLINE" : "AVAILABLE")}
          />
          {me.data && me.data.status !== "ACTIVE" ? (
            <Text variant="bodySmall" color={colors.error}>Your account is {me.data.status.toLowerCase()}. Contact support.</Text>
          ) : null}
        </View>
      )}

      <View style={styles.tabs}>
        {(["active", "history", "earnings"] as Tab[]).map((t) => (
          <Pressable key={t} onPress={() => setTab(t)} style={[styles.tab, tab === t && styles.tabOn]} accessibilityRole="tab">
            <Text variant="bodyMedium" color={tab === t ? colors.textInverse : colors.primary}>
              {t === "active" ? "Gigs" : t === "history" ? "History" : "Earnings"}
            </Text>
          </Pressable>
        ))}
      </View>

      {tab === "earnings" ? (
        earnings.isLoading ? <ActivityIndicator color={colors.primary} /> :
        earnings.isError ? (
          <EmptyState icon="wifi-off" title="Couldn't load earnings" actionLabel="Retry" onAction={() => earnings.refetch()} />
        ) : (
          <FlatList
            data={earnings.data?.items ?? []}
            keyExtractor={(e) => String(e.id)}
            ListHeaderComponent={<Text variant="h2" style={styles.pad}>Total {rupees(earnings.data?.total ?? "0")}</Text>}
            ListEmptyComponent={<EmptyState icon="dollar-sign" title="No earnings yet" message="Complete a delivery to earn." />}
            renderItem={({ item }) => (
              <View style={styles.card}>
                <View style={{ flex: 1 }}>
                  <Text variant="bodyMedium">Order #{item.order_id}</Text>
                  <Text variant="bodySmall" color={colors.textSecondary}>{item.billable_km} km - {new Date(item.created_at).toLocaleDateString()}</Text>
                </View>
                <Text variant="bodyMedium" color={colors.success}>{rupees(item.amount)}</Text>
              </View>
            )}
          />
        )
      ) : list.isLoading ? (
        <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.xl }} />
      ) : list.isError ? (
        <EmptyState icon="wifi-off" title="Couldn't load deliveries" message={toApiError(list.error).message} actionLabel="Retry" onAction={() => list.refetch()} />
      ) : (
        <FlatList
          data={list.data?.items ?? []}
          keyExtractor={(a) => String(a.id)}
          renderItem={renderJob}
          refreshing={list.isRefetching}
          onRefresh={() => list.refetch()}
          ListEmptyComponent={
            <EmptyState icon="truck" title={tab === "active" ? "No deliveries right now" : "No past deliveries"} message={tab === "active" ? "New jobs show up here when dispatch assigns them." : undefined} />
          }
        />
      )}
    </Screen>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat}>
      <Text variant="h2" color={colors.primary}>{value}</Text>
      <Text variant="bodySmall" color={colors.textSecondary}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", padding: spacing.xl },
  pad: { paddingHorizontal: spacing.xl, paddingBottom: spacing.md },
  statsRow: { flexDirection: "row", marginBottom: spacing.md },
  stat: { flex: 1, backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing.md, marginRight: spacing.sm, alignItems: "center" },
  tabs: { flexDirection: "row", paddingHorizontal: spacing.xl, marginVertical: spacing.md },
  tab: { flex: 1, paddingVertical: spacing.sm, alignItems: "center", borderRadius: radius.md, marginRight: spacing.sm, backgroundColor: colors.surfaceTint },
  tabOn: { backgroundColor: colors.primary },
  card: { flexDirection: "row", alignItems: "center", backgroundColor: colors.surface, marginHorizontal: spacing.xl, marginBottom: spacing.sm, padding: spacing.md, borderRadius: radius.md },
  pill: { backgroundColor: colors.primaryLight, paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: radius.md },
});
