import React, { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Share, StyleSheet, TextInput, View } from "react-native";
import { Stack } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { referralApi, toApiError } from "@/api";
import { useToastStore } from "@/store/toastStore";
import { colors, radius, spacing } from "@/theme";

const rupees = (v: string) => `Rs ${Number(v).toFixed(0)}`;

const STATUS_LABEL: Record<string, string> = {
  PENDING: "Waiting for first order",
  QUALIFIED: "Order done - reward on hold",
  REWARDED: "Reward earned",
  REVERSED: "Reward reversed",
  CANCELLED: "Expired",
};

/** Refer & Earn. Every amount, window and rule on this screen comes from the
 * server (GET /referrals/me) - nothing is hard-coded here. */
export default function ReferScreen() {
  const qc = useQueryClient();
  const show = useToastStore((s) => s.show);
  const [friendCode, setFriendCode] = useState("");
  const me = useQuery({ queryKey: ["referral", "me"], queryFn: referralApi.me });
  const history = useQuery({ queryKey: ["referral", "history"], queryFn: referralApi.history });

  const apply = useMutation({
    mutationFn: () => referralApi.apply(friendCode.trim()),
    onSuccess: (r) => {
      show(`Code added - ${r.referrer_display_name} invited you`, "success");
      setFriendCode("");
      qc.invalidateQueries({ queryKey: ["referral"] });
    },
    onError: (e) => show(toApiError(e).message, "error"),
  });

  const data = me.data;

  const share = async () => {
    if (!data?.share_message) return;
    try {
      await Share.share({ message: data.share_message });
    } catch {
      show("Could not open sharing", "error");
    }
  };
  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: "Refer & Earn" }} />
      {me.isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : me.isError || !data ? (
        <View style={styles.center}>
          <EmptyState
            icon="wifi-off"
            title="Couldn't load Refer & Earn"
            message={toApiError(me.error).message}
            actionLabel="Try again"
            onAction={() => me.refetch()}
          />
        </View>
      ) : !data.program.enabled ? (
        <View style={styles.center}>
          <EmptyState
            icon="gift"
            title="Coming soon"
            message="Refer & Earn is not available right now. Check back soon."
          />
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.content}>
          <View style={styles.hero}>
            <Text variant="eyebrow" color={colors.accent}>
              YOUR CODE
            </Text>
            <Text variant="displayM" color={colors.textInverse} style={styles.code} accessibilityLabel={`Your referral code ${data.code}`}>
              {data.code}
            </Text>
            <Text variant="bodySmall" color="rgba(255,255,255,0.85)" align="center">
              Friends get {rupees(data.program.referred_reward)}, you get {rupees(data.program.referrer_reward)}.
            </Text>
            <View style={styles.row}>
              <Button label="Share" onPress={share} icon={<Feather name="share-2" size={16} color={colors.textInverse} />} style={{ flex: 1 }} />
            </View>
          </View>

          <Text variant="eyebrow" color={colors.textSecondary} style={styles.label}>
            HOW IT WORKS
          </Text>
          {[
            "Share your code with a friend who is new to Gawacha Bazaar.",
            `They add it within ${data.program.apply_window_days} days of joining, before their first order.`,
            `When their order of ${rupees(data.program.min_order_value)} or more is delivered (within ${data.program.qualify_window_days} days), you both earn.`,
          ].map((t, i) => (
            <View key={i} style={styles.step}>
              <View style={styles.stepNo}>
                <Text variant="bodyMedium" color={colors.primary}>{i + 1}</Text>
              </View>
              <Text variant="body" style={{ flex: 1 }}>{t}</Text>
            </View>
          ))}

          <Text variant="eyebrow" color={colors.textSecondary} style={styles.label}>
            YOUR REFERRALS
          </Text>
          <View style={styles.stats}>
            <Stat label="Invited" value={String(data.stats.total_referrals)} />
            <Stat label="Rewarded" value={String(data.stats.rewarded)} />
            <Stat label="Earned" value={rupees(data.stats.total_earned)} />
          </View>

          {history.isLoading ? (
            <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.lg }} />
          ) : history.isError ? (
            <Pressable onPress={() => history.refetch()} accessibilityRole="button">
              <Text variant="body" color={colors.error} style={{ marginTop: spacing.md }}>
                Couldn't load your referrals. Tap to retry.
              </Text>
            </Pressable>
          ) : history.data && history.data.items.length > 0 ? (
            history.data.items.map((h) => (
              <View key={h.id} style={styles.histRow}>
                <View style={{ flex: 1 }}>
                  <Text variant="bodyMedium">{h.referred_display_name}</Text>
                  <Text variant="bodySmall" color={colors.textSecondary}>{STATUS_LABEL[h.status] ?? h.status}</Text>
                </View>
                {h.reward_amount ? <Text variant="bodyMedium" color={colors.success}>{rupees(h.reward_amount)}</Text> : null}
              </View>
            ))
          ) : (
            <Text variant="body" color={colors.textSecondary} style={{ marginTop: spacing.md }}>
              No referrals yet. Share your code to get started.
            </Text>
          )}

          {data.can_apply_code ? (
            <>
              <Text variant="eyebrow" color={colors.textSecondary} style={styles.label}>
                HAVE A FRIEND'S CODE?
              </Text>
              <TextInput
                value={friendCode}
                onChangeText={(t) => setFriendCode(t.replace(/[^A-Za-z0-9]/g, "").toUpperCase())}
                placeholder="Enter code"
                autoCapitalize="characters"
                autoCorrect={false}
                maxLength={16}
                style={styles.input}
                accessibilityLabel="Friend's referral code"
              />
              <Button
                label="Apply code"
                onPress={() => apply.mutate()}
                loading={apply.isPending}
                disabled={friendCode.length < 6}
              />
            </>
          ) : data.apply_blocked_reason ? (
            <Text variant="bodySmall" color={colors.textSecondary} style={{ marginTop: spacing.xl }}>
              {data.already_referred ? "You joined with a friend's code." : data.apply_blocked_reason}
            </Text>
          ) : null}
        </ScrollView>
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
  center: { flex: 1, justifyContent: "center", alignItems: "center", padding: spacing.xl },
  content: { padding: spacing.xl, paddingBottom: spacing["2xl"] * 2 },
  hero: { backgroundColor: colors.primary, borderRadius: radius.lg, padding: spacing.xl, alignItems: "center" },
  code: { letterSpacing: 4, marginVertical: spacing.sm },
  row: { flexDirection: "row", marginTop: spacing.lg, alignSelf: "stretch" },
  label: { marginTop: spacing.xl, marginBottom: spacing.sm },
  step: { flexDirection: "row", alignItems: "center", marginBottom: spacing.sm },
  stepNo: { width: 28, height: 28, borderRadius: 14, backgroundColor: colors.primaryLight, alignItems: "center", justifyContent: "center", marginRight: spacing.md },
  stats: { flexDirection: "row", justifyContent: "space-between" },
  stat: { flex: 1, backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing.md, marginRight: spacing.sm, alignItems: "center" },
  histRow: { flexDirection: "row", alignItems: "center", paddingVertical: spacing.md, borderBottomWidth: 1, borderColor: colors.divider },
  input: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, backgroundColor: colors.surface, marginBottom: spacing.md, letterSpacing: 3 },
});
