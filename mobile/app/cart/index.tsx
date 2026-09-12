import React from "react";
import { FlatList, Pressable, StyleSheet, View } from "react-native";
import { Stack, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { QuantityStepper } from "@/components/QuantityStepper";
import { formatMoney } from "@/utils/money";
import {
  useCart,
  useRemoveCartItem,
  useUpdateCartItemQuantity,
} from "@/features/cart/useCart";
import { colors, radius, spacing } from "@/theme";
import { CartItemResponse } from "@/types/api";

export default function CartScreen() {
  const router = useRouter();
  const { data: cart, isLoading } = useCart();
  const updateItem = useUpdateCartItemQuantity();
  const removeItem = useRemoveCartItem();

  const items = cart?.items ?? [];

  return (
    <Screen>
      <Stack.Screen options={{ headerShown: true, title: "Your cart" }} />
      {!isLoading && items.length === 0 ? (
        <EmptyState
          icon="shopping-cart"
          title="Your cart is empty"
          message="Find something you'll love."
          actionLabel="Start shopping"
          onAction={() => router.replace("/(tabs)")}
        />
      ) : (
        <>
          <FlatList
            data={items}
            keyExtractor={(item) => String(item.id)}
            contentContainerStyle={styles.list}
            renderItem={({ item }) => (
              <CartRow
                item={item}
                onIncrement={() => updateItem.mutate({ itemId: item.id, quantity: Math.round(Number.parseFloat(item.quantity)) + 1 })}
                onDecrement={() => {
                  const qty = Math.round(Number.parseFloat(item.quantity));
                  if (qty <= 1) removeItem.mutate(item.id);
                  else updateItem.mutate({ itemId: item.id, quantity: qty - 1 });
                }}
                onRemove={() => removeItem.mutate(item.id)}
              />
            )}
          />
          <View style={styles.summary}>
            <View style={styles.summaryRow}>
              <Text variant="bodyLarge">Total</Text>
              <Text variant="h2">{formatMoney(cart?.total_amount ?? "0", cart?.currency ?? "INR")}</Text>
            </View>
            <Text variant="caption" color={colors.textMuted} style={styles.summaryNote}>
              Final total is confirmed at checkout.
            </Text>
            <Button label="Proceed to checkout" onPress={() => router.push("/checkout")} fullWidth size="lg" />
          </View>
        </>
      )}
    </Screen>
  );
}

function CartRow({
  item,
  onIncrement,
  onDecrement,
  onRemove,
}: {
  item: CartItemResponse;
  onIncrement: () => void;
  onDecrement: () => void;
  onRemove: () => void;
}) {
  const quantity = Math.round(Number.parseFloat(item.quantity));
  return (
    <View style={styles.row}>
      <View style={styles.rowInfo}>
        <Text variant="bodyMedium" numberOfLines={2}>
          {item.product_name}
        </Text>
        <Text variant="caption" color={colors.textSecondary}>
          {item.variant_name}
        </Text>
        {item.unit_price ? (
          <Text variant="bodySmall" color={colors.textSecondary} style={{ marginTop: spacing.xs }}>
            {formatMoney(item.unit_price, item.currency ?? "INR")} each
          </Text>
        ) : (
          <Text variant="bodySmall" color={colors.error} style={{ marginTop: spacing.xs }}>
            Price no longer available
          </Text>
        )}
      </View>
      <View style={styles.rowActions}>
        <QuantityStepper quantity={quantity} onAdd={onIncrement} onIncrement={onIncrement} onDecrement={onDecrement} />
        <Pressable onPress={onRemove} hitSlop={8} style={styles.removeButton}>
          <Feather name="trash-2" size={15} color={colors.textMuted} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.base },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.base,
    marginBottom: spacing.md,
  },
  rowInfo: { flex: 1, marginRight: spacing.md },
  rowActions: { alignItems: "flex-end", justifyContent: "space-between" },
  removeButton: { marginTop: spacing.md },
  summary: {
    padding: spacing.base,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
  },
  summaryRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.xs },
  summaryNote: { marginBottom: spacing.base },
});
