import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Alert, Linking, ScrollView, StyleSheet, TextInput, View } from "react-native";
import { Stack, useLocalSearchParams } from "expo-router";
import * as Location from "expo-location";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { partnerApi, toApiError, type Assignment } from "@/api";
import { useToastStore } from "@/store/toastStore";
import { colors, radius, spacing } from "@/theme";

const rupees = (v: string) => `Rs ${Number(v).toFixed(0)}`;
const LOCATION_EVERY_MS = 10_000;

/** One delivery: customer + address, maps deep link, the single next step,
 * COD cash confirmation and a "could not deliver" path. Location is shared
 * only while the job is picked up / out for delivery. */
export default function DeliveryDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const aid = Number(id);
  const qc = useQueryClient();
  const show = useToastStore((s) => s.show);
  const [cash, setCash] = useState("");
  const [failReason, setFailReason] = useState("");
  const [showFail, setShowFail] = useState(false);

  const q = useQuery({ queryKey: ["partner", "job", aid], queryFn: () => partnerApi.get(aid), enabled: Number.isFinite(aid) });
  const job = q.data;

  const refresh = (a: Assignment) => {
    qc.setQueryData(["partner", "job", aid], a);
    qc.invalidateQueries({ queryKey: ["partner", "list"] });
    qc.invalidateQueries({ queryKey: ["partner", "me"] });
  };
  const onError = (e: unknown) => show(toApiError(e).message, "error");
  const step = useMutation({ mutationFn: (a: "accept" | "pickup" | "out-for-delivery") => partnerApi.act(aid, a), onSuccess: refresh, onError });
  const reject = useMutation({ mutationFn: () => partnerApi.reject(aid, "Declined by partner"), onSuccess: refresh, onError });
  const fail = useMutation({ mutationFn: () => partnerApi.fail(aid, failReason.trim()), onSuccess: refresh, onError });
  const deliver = useMutation({
    mutationFn: () => partnerApi.deliver(aid, job?.cod_status === "COD_PENDING" ? cash.trim() : undefined),
    onSuccess: (a) => { refresh(a); show("Delivery completed", "success"); },
    onError,
  });

  // Share location only during an active hand-over; stops when the status changes or the screen closes.
  const sharing = job?.status === "PICKED_UP" || job?.status === "OUT_FOR_DELIVERY";
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (!sharing) return;
    let cancelled = false;
    (async () => {
      const perm = await Location.requestForegroundPermissionsAsync();
      if (perm.status !== "granted" || cancelled) return;
      const push = async () => {
        try {
          const p = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
          await partnerApi.location(aid, p.coords.latitude, p.coords.longitude, p.coords.accuracy);
        } catch {
          /* 429 / transient: the next tick retries */
        }
      };
      push();
      timer.current = setInterval(push, LOCATION_EVERY_MS);
    })();
    return () => {
      cancelled = true;
      if (timer.current) clearInterval(timer.current);
    };
  }, [sharing, aid]);

  const next: { label: string; run: () => void; loading: boolean } | null = !job
    ? null
    : job.status === "ASSIGNED"
      ? { label: "Accept delivery", run: () => step.mutate("accept"), loading: step.isPending }
      : job.status === "ACCEPTED"
        ? { label: "Picked up from hub", run: () => step.mutate("pickup"), loading: step.isPending }
        : job.status === "PICKED_UP"
          ? { label: "Start delivery", run: () => step.mutate("out-for-delivery"), loading: step.isPending }
          : null;

  const confirmDeliver = () => {
    if (job?.cod_status === "COD_PENDING") {
      if (Number(cash) !== Number(job.cod_expected_amount)) {
        Alert.alert("Check the cash", `Enter exactly ${rupees(job.cod_expected_amount)} - the amount due for this order.`);
        return;
      }
    }
    Alert.alert("Complete delivery?", "This cannot be undone.", [
      { text: "Cancel", style: "cancel" },
      { text: "Complete", onPress: () => deliver.mutate() },
    ]);
  };

  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: job ? `Order #${job.order_number}` : "Delivery" }} />
      {q.isLoading ? (
        <ActivityIndicator color={colors.primary} style={{ marginTop: spacing["2xl"] }} />
      ) : q.isError || !job ? (
        <EmptyState icon="alert-circle" title="Couldn't load this delivery" message={toApiError(q.error).message} actionLabel="Retry" onAction={() => q.refetch()} />
      ) : (
        <ScrollView contentContainerStyle={styles.content}>
          <Text variant="eyebrow" color={colors.accentDark}>{job.status.replace(/_/g, " ")}</Text>
          {job.customer_name ? <Text variant="h2">{job.customer_name}</Text> : null}
          {job.address ? (
            <Text variant="body" style={styles.gap}>
              {[job.address.address_line_1, job.address.address_line_2, job.address.city, job.address.postal_code].filter(Boolean).join(", ")}
            </Text>
          ) : null}
          {job.maps_url ? <Button label="Open in Maps" variant="outline" onPress={() => Linking.openURL(job.maps_url as string)} /> : null}

          <Text variant="eyebrow" color={colors.textSecondary} style={styles.gap}>ITEMS</Text>
          {job.items.map((it, i) => (
            <Text key={i} variant="body">{it.quantity} {it.unit ?? ""} - {it.name}</Text>
          ))}

          {job.cod_status !== "NOT_APPLICABLE" ? (
            <View style={styles.cod}>
              <Text variant="bodyMedium">Cash on delivery</Text>
              <Text variant="displayM" color={colors.primary}>{rupees(job.cod_expected_amount)}</Text>
              <Text variant="bodySmall" color={colors.textSecondary}>
                {job.cod_status === "COD_COLLECTED" ? "Collected" : job.cod_status === "COD_FAILED" ? "Not collected" : "Collect exactly this amount."}
              </Text>
            </View>
          ) : null}

          {job.status === "DELIVERED" && job.earning_amount ? (
            <Text variant="bodyMedium" color={colors.success} style={styles.gap}>You earned {rupees(job.earning_amount)}</Text>
          ) : null}
          {job.close_reason && job.status !== "DELIVERED" ? <Text variant="bodySmall" color={colors.textSecondary}>{job.close_reason}</Text> : null}

          {next ? <Button label={next.label} onPress={next.run} loading={next.loading} style={styles.gap} /> : null}

          {job.status === "OUT_FOR_DELIVERY" ? (
            <View style={styles.gap}>
              {job.cod_status === "COD_PENDING" ? (
                <TextInput value={cash} onChangeText={(t) => setCash(t.replace(/[^0-9.]/g, ""))} keyboardType="decimal-pad" placeholder="Cash collected (Rs)" style={styles.input} accessibilityLabel="Cash collected" />
              ) : null}
              <Button label="Delivered" onPress={confirmDeliver} loading={deliver.isPending} disabled={job.cod_status === "COD_PENDING" && cash.length === 0} />
            </View>
          ) : null}

          {job.status === "ASSIGNED" ? (
            <Button label="Decline" variant="ghost" onPress={() => reject.mutate()} loading={reject.isPending} />
          ) : null}
          {job.status === "PICKED_UP" || job.status === "OUT_FOR_DELIVERY" ? (
            showFail ? (
              <View style={styles.gap}>
                <TextInput value={failReason} onChangeText={setFailReason} placeholder="Why could it not be delivered?" style={styles.input} maxLength={300} />
                <Button label="Mark as not delivered" variant="danger" onPress={() => fail.mutate()} loading={fail.isPending} disabled={failReason.trim().length < 3} />
              </View>
            ) : (
              <Button label="Could not deliver" variant="ghost" onPress={() => setShowFail(true)} />
            )
          ) : null}
        </ScrollView>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.xl, paddingBottom: spacing["2xl"] * 2 },
  gap: { marginTop: spacing.lg },
  cod: { backgroundColor: colors.warningLight, borderRadius: radius.md, padding: spacing.lg, marginTop: spacing.lg },
  input: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, backgroundColor: colors.surface, marginBottom: spacing.md },
});
