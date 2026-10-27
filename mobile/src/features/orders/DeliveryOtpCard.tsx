import React, { useEffect, useState } from "react";
import { StyleSheet, View } from "react-native";
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

/** The customer's side of proof-of-delivery. The code is shown only while ACTIVE
 * and only to the order's owner (the backend enforces both). */
export function DeliveryOtpCard({ data }: { data: DeliveryOtp }) {
  const left = useCountdown(data.expires_at, data.seconds_left);
  if (!data.required && data.status !== "VERIFIED") return null;

  const active = data.status === "ACTIVE" && left > 0;
  const expired = data.status === "EXPIRED" || (data.status === "ACTIVE" && left === 0);

  return (
    <View style={styles.card} accessibilityLabel="Delivery code">
      <View style={styles.row}>
        <Feather name={data.status === "VERIFIED" ? "check-circle" : "lock"} size={18} color={colors.primary} />
        <Text variant="bodyMedium" color={colors.primary}>Delivery code</Text>
      </View>
      {active && data.otp ? (
        <>
          <Text variant="displayM" color={colors.primary} style={styles.code} selectable={false}>
            {data.otp.split("").join(" ")}
          </Text>
          <Text variant="bodySmall" color={colors.textSecondary}>
            Share this code with the delivery partner only when your order is physically delivered. Do not share it
            with anyone else. Shown time left: {pad(Math.floor(left / 60))}:{pad(left % 60)} (the server decides if a code is still valid).
          </Text>
        </>
      ) : data.status === "VERIFIED" ? (
        <Text variant="bodySmall" color={colors.success}>Code verified - your order was handed over.</Text>
      ) : data.status === "LOCKED" ? (
        <Text variant="bodySmall" color={colors.error}>Too many wrong attempts. Ask the delivery partner to send a new code.</Text>
      ) : expired ? (
        <Text variant="bodySmall" color={colors.textSecondary}>This code has expired. Ask the delivery partner to send a new one.</Text>
      ) : (
        <Text variant="bodySmall" color={colors.textSecondary}>
          Your code appears here once your order is out for delivery. Give it to the delivery partner only when you receive your order.
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.warningLight, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.lg },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.sm },
  code: { fontSize: 34, letterSpacing: 4, textAlign: "center", marginVertical: spacing.md },
});
