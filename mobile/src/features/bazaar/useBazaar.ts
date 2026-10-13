import { useQuery } from "@tanstack/react-query";
import { bazaarApi } from "@/api";
import { useCart } from "@/features/cart/useCart";
import { useAuthStore } from "@/store/authStore";

/** Different products in the cart - what counts toward a Bazaar (the same
 * product in two sizes counts once; mirrors the backend rule). */
export function useCartProductCount(): number {
  const { data } = useCart();
  return new Set(data?.items.map((i) => i.product_id) ?? []).size;
}

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
  const itemCount = useCartProductCount();
  return useQuery({
    queryKey: ["bazaar", "quote", addressId, itemCount],
    queryFn: () => bazaarApi.deliveryQuote(addressId),
    enabled: signedIn && itemCount > 0,
    staleTime: 30_000,
  });
}
