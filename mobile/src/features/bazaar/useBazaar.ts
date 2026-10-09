import { useQuery } from "@tanstack/react-query";
import { bazaarApi } from "@/api";
import { useCartItemCount } from "@/features/cart/useCart";
import { useAuthStore } from "@/store/authStore";

/** Progress toward Gawacha Bazaar+ (signed-in customers only). */
export function useBazaarStatus() {
  const signedIn = useAuthStore((s) => s.status === "authenticated");
  return useQuery({
    queryKey: ["bazaar", "status"],
    queryFn: bazaarApi.status,
    enabled: signedIn,
    staleTime: 60_000,
  });
}

/** What delivering the current cart to `addressId` costs. Re-fetches when
 * the cart's unit count or the chosen address changes. */
export function useDeliveryQuote(addressId: number | null) {
  const signedIn = useAuthStore((s) => s.status === "authenticated");
  const itemCount = useCartItemCount();
  return useQuery({
    queryKey: ["bazaar", "quote", addressId, itemCount],
    queryFn: () => bazaarApi.deliveryQuote(addressId),
    enabled: signedIn && itemCount > 0,
    staleTime: 30_000,
  });
}
