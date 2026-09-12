import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cartApi } from "@/api";
import { CartResponse } from "@/types/api";

export const cartQueryKey = ["cart"] as const;

/**
 * Cart is server-owned (Phase 13/18 rule: never trust a client-computed
 * total). This hook's job is to keep the UI responsive - optimistic
 * local updates on mutation - while always reconciling back to whatever
 * the server actually returns, including on error (via invalidate).
 */
export function useCart() {
  return useQuery({
    queryKey: cartQueryKey,
    queryFn: cartApi.get,
    staleTime: 15_000,
  });
}

export function useCartItemCount(): number {
  const { data } = useCart();
  if (!data) return 0;
  return data.items.reduce((sum, item) => sum + Math.round(Number.parseFloat(item.quantity)), 0);
}

/** Current cart quantity for a variant, or 0 if not in the cart. */
export function useCartQuantityForVariant(variantId: number): number {
  const { data } = useCart();
  const item = data?.items.find((i) => i.variant_id === variantId);
  return item ? Math.round(Number.parseFloat(item.quantity)) : 0;
}

export function useAddToCart() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ variantId, quantity }: { variantId: number; quantity: number }) =>
      cartApi.addItem(variantId, String(quantity)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cartQueryKey }),
  });
}

export function useUpdateCartItemQuantity() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, quantity }: { itemId: number; quantity: number }) =>
      cartApi.updateItem(itemId, String(quantity)),
    onMutate: async ({ itemId, quantity }) => {
      await queryClient.cancelQueries({ queryKey: cartQueryKey });
      const previous = queryClient.getQueryData<CartResponse>(cartQueryKey);
      if (previous) {
        queryClient.setQueryData<CartResponse>(cartQueryKey, {
          ...previous,
          items: previous.items.map((i) => (i.id === itemId ? { ...i, quantity: String(quantity) } : i)),
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(cartQueryKey, context.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: cartQueryKey }),
  });
}

export function useRemoveCartItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (itemId: number) => cartApi.removeItem(itemId),
    onMutate: async (itemId) => {
      await queryClient.cancelQueries({ queryKey: cartQueryKey });
      const previous = queryClient.getQueryData<CartResponse>(cartQueryKey);
      if (previous) {
        queryClient.setQueryData<CartResponse>(cartQueryKey, {
          ...previous,
          items: previous.items.filter((i) => i.id !== itemId),
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(cartQueryKey, context.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: cartQueryKey }),
  });
}

export function useClearCart() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cartApi.clear,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cartQueryKey }),
  });
}

/** Add-to-cart / stepper convenience that resolves the right mutation
 * (add vs. update-by-item vs. remove-at-zero) from a variant id, so
 * ProductCard/ProductDetail don't need to know cart-item ids. */
export function useVariantStepper(variantId: number) {
  const { data: cart } = useCart();
  const add = useAddToCart();
  const update = useUpdateCartItemQuantity();
  const remove = useRemoveCartItem();

  const item = cart?.items.find((i) => i.variant_id === variantId);
  const quantity = item ? Math.round(Number.parseFloat(item.quantity)) : 0;

  return {
    quantity,
    isMutating: add.isPending || update.isPending || remove.isPending,
    add: () => add.mutate({ variantId, quantity: 1 }),
    increment: () => {
      if (item) update.mutate({ itemId: item.id, quantity: quantity + 1 });
      else add.mutate({ variantId, quantity: 1 });
    },
    decrement: () => {
      if (!item) return;
      if (quantity <= 1) remove.mutate(item.id);
      else update.mutate({ itemId: item.id, quantity: quantity - 1 });
    },
  };
}
