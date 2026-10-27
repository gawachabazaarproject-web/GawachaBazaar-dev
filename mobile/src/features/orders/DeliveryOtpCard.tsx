import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import type { DeliveryOtp } from "@/api/orderApi";
import { colors, radius, spacing } from "@/theme";

const pad = (n: number) => String(n).padStart(2, "0");

/** Display only: the backend is authoritative for expiry. Seconds left until `expiresAt`, ticking once a second (0 when expired). */
function useCountdown(expiresAt: string | null, fallback: number | null): number {
  const target = expiresAt ? Date.parse(expiresAt) : NaN;
  const calc = () => (Number.isFinite(target) ? Math.max(0, Math.ceil((target - Date.now()) / 1000)) : (fallback ?? 0));
  const [left, setLeft] = useState(calc);
  useEffect(() => {
    setLeft(calc());
    const t = setInterval(() => setLeft(calc()), 1000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiresAt]);
  return left;
}

/** Proof-of-delivery code for the customer. Shown only while the order is open
 * (waiting / active / expired / locked) and gone once the delivery is finished.
 * The code is returned only to the order's owner and only while ACTIVE (the backend enforces both). */
export function DeliveryOtpCard({
  data,
  orderLabel,
  onPress,
}: {
  data: DeliveryOtp;
  orderLabel?: string;
  onPress?: () => void;
}) {
  const left = useCountdown(data.expires_at, data.seconds_left);
  const open = data.required && ["WAITING", "ACTIVE", "EXPIRED", "LOCKED"].includes(data.status);
  if (!open) return null;

  const active = data.status === "ACTIVE" && !!data.otp && left > 0;
  const Wrapper = onPress ? Pressable : View;

  return (
    <Wrapper style={[styles.card, active ? styles.cardActive : styles.cardIdle]} onPress={onPress} accessibilityLabel="Delivery code">
      <View style={styles.row}>
        <Feather name="shield" size={18} color={active ? colors.accent : colors.primary} />
        <Text variant="bodyMedium" color={active ? colors.textInverse : colors.primary}>
          Delivery code{orderLabel ? ` - ${orderLabel}` : ""}
        </Text>
      </View>
      {active ? (
        <>
          <Text variant="displayM" color={colors.textInverse} style={styles.code} selectable={false}>
            {data.otp!.split("").join(" ")}
          </Text>
          <Text variant="bodySmall" color={colors.textInverse} style={styles.help}>
            Tell this code to the delivery partner only when you have received your order.
            {" "}Valid for {pad(Math.floor(left / 60))}:{pad(left % 60)}.
          </Text>
        </>
      ) : data.status === "LOCKED" ? (
        <Text variant="bodySmall" color={colors.error}>Too many wrong attempts. Ask the delivery partner to send a new code.</Text>
      ) : data.status === "EXPIRED" || (data.status === "ACTIVE" && left === 0) ? (
        <Text variant="bodySmall" color={colors.textSecondary}>This code has expired. Ask the delivery partner to send a new one.</Text>
      ) : (
        <Text variant="bodySmall" color={colors.textSecondary}>
          Your code will appear here as soon as your order is out for delivery.
        </Text>
      )}
    </Wrapper>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.lg },
  cardActive: { backgroundColor: colors.primary },
  cardIdle: { backgroundColor: colors.warningLight },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.sm },
  code: { fontSize: 40, letterSpacing: 6, textAlign: "center", marginVertical: spacing.md },
  help: { textAlign: "center", opacity: 0.9 },
});
