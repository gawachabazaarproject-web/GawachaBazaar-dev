import React, { useEffect } from "react";
import { StyleSheet, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import Animated, { useSharedValue, withSequence, withSpring, useAnimatedStyle } from "react-native-reanimated";
import * as Haptics from "expo-haptics";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { useOrder } from "@/features/orders/useOrders";
import { formatMoney } from "@/utils/money";
import { colors, radius, spacing, springs } from "@/theme";

/**
 * Order success (brief §29): a single tasteful confirmation moment, not a
 * celebratory animation. A checkmark that settles into place with a
 * spring, one haptic pulse, and the essential facts a customer needs.
 */
export default function OrderSuccessScreen() {
  const { orderId } = useLocalSearchParams<{ orderId: string }>();
  const router = useRouter();
  const { data: order } = useOrder(Number(orderId));

  const scale = useSharedValue(0.6);
  useEffect(() => {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    scale.value = withSequence(withSpring(1.08, springs.gentle), withSpring(1, springs.snappy));
  }, [scale]);
  const animatedStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));

  return (
    <Screen>
      <View style={styles.content}>
        <Animated.View style={[styles.iconCircle, animatedStyle]}>
          <Feather name="check" size={40} color={colors.textInverse} />
        </Animated.View>

        <Text variant="h1" align="center" style={styles.title}>
          Order placed
        </Text>
        <Text variant="body" color={colors.textSecondary} align="center" style={styles.subtitle}>
          We've received your order and are getting it ready.
        </Text>

        {order ? (
          <View style={styles.detailsCard}>
            <DetailRow label="Order number" value={order.order_number} />
            <DetailRow label="Total" value={formatMoney(order.total_amount, order.currency)} />
            <DetailRow label="Estimated delivery" value="Within a few hours" />
          </View>
        ) : null}

        <View style={styles.actions}>
          <Button label="Track order" onPress={() => router.replace(`/order/${orderId}`)} fullWidth size="lg" />
          <Button
            label="Continue shopping"
            variant="ghost"
            onPress={() => router.replace("/(tabs)")}
            style={{ marginTop: spacing.sm }}
          />
        </View>
      </View>
    </Screen>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <Text variant="body" color={colors.textSecondary}>
        {label}
      </Text>
      <Text variant="bodyMedium">{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  iconCircle: {
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: colors.success,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.xl,
  },
  title: { marginBottom: spacing.xs },
  subtitle: { marginBottom: spacing.xl, maxWidth: 280 },
  detailsCard: {
    width: "100%",
    backgroundColor: colors.surface,
    borderRadius: radius.none,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.base,
    marginBottom: spacing.xl,
  },
  detailRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: spacing.sm },
  actions: { width: "100%" },
});
