import React from "react";
import { View } from "react-native";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { orderApi } from "@/api";
import { DeliveryOtpCard } from "@/features/orders/DeliveryOtpCard";
import { useDeliveryOtp } from "@/features/orders/useOrders";
import { spacing } from "@/theme";

function OrderCode({ id, number }: { id: number; number: string }) {
  const router = useRouter();
  const { data } = useDeliveryOtp(id, true);
  if (!data) return null;
  return <DeliveryOtpCard data={data} orderLabel={`#${number}`} onPress={() => router.push(`/order/${id}` as never)} />;
}

/** Home-screen banner: the delivery code for each open (confirmed) order, so the
 * customer sees it without opening the order. Renders nothing when there is none,
 * and an order disappears from it the moment it is completed. */
export function ActiveDeliveryCodes() {
  const { data } = useQuery({
    queryKey: ["orders", "open-for-code"],
    queryFn: () => orderApi.list(1, 10),
    refetchInterval: 15_000,
  });
  const open = (data?.items ?? []).filter((o) => o.status === "CONFIRMED").slice(0, 3);
  if (open.length === 0) return null;
  return (
    <View style={{ paddingHorizontal: spacing.lg, marginTop: spacing.md }}>
      {open.map((o) => (
        <OrderCode key={o.id} id={o.id} number={o.order_number} />
      ))}
    </View>
  );
}
