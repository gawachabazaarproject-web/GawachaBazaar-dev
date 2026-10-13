import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cartApi, toApiError } from "@/api";
import { useToastStore } from "@/store/toastStore";
import { CartItemResponse, CartResponse } from "@/types/api";

/**
 * Preview a promo code (or the best automatic promotion) against the
 * current cart. Calls the same backend engine checkout itself uses
 * (`PromotionService.evaluate_for_cart`), so the discount shown here can
 * never disagree with what checkout actually charges - this hook never
 * computes a discount locally.
 */
export function useEvaluatePromo() {
  return useMutation({
    mutationFn: (promoCode: string | null) => cartApi.evaluatePromo(promoCode),
  });
}

export const cartQueryKey = ["cart"] as const;

/**
 * Cart is server-owned (Phase 13/18 rule: never trust a client-computed
 * total). This hook's job is to keep the UI responsive - optimistic
 * local updates on mutation - while always reconciling back to whatever
 * the server actually returns, including on error (via invalidate).
 */
export function useCart(enabled: boolean = true) {
  return useQuery({
    queryKey: cartQueryKey,
    queryFn: cartApi.get,
    staleTime: 15_000,
    enabled,
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

/** What the UI already knows about a product, used to show it in the cart
 * instantly while the server confirms the add. */
export type CartItemPreview = Omit<CartItemResponse, "id" | "variant_id" | "quantity" | "line_total">;

function withTotals(cart: CartResponse, items: CartItemResponse[]): CartResponse {
  const total = items.reduce((sum, i) => sum + Number.parseFloat(i.line_total ?? "0"), 0);
  return { ...cart, items, total_amount: total.toFixed(2) };
}

/** Adds still waiting on the server, by variant. Taps on a card's stepper
 * made before the add returns can't call the API yet (no real item id), so
 * they only record the quantity the customer wants in `desiredQty`, show it
 * immediately, and get synced once the add has landed. */
const pendingAdds = new Map<number, Promise<CartItemResponse | null>>();
const desiredQty = new Map<number, number>();

/** Refetch the cart only once the last in-flight cart change has finished -
 * a refetch per tap queues several slow round trips behind each other, and
 * each mutation already returns/applies its own result. */
function invalidateWhenIdle(queryClient: ReturnType<typeof useQueryClient>) {
  if (queryClient.isMutating() > 1) return;
  void queryClient.invalidateQueries({ queryKey: cartQueryKey });
}

export function useAddToCart() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ variantId, quantity }: { variantId: number; quantity: number; preview?: CartItemPreview }) =>
      cartApi.addItem(variantId, String(quantity)),
    onMutate: async ({ variantId, quantity, preview }) => {
      if (!preview) return { previous: undefined };
      await queryClient.cancelQueries({ queryKey: cartQueryKey });
      const previous = queryClient.getQueryData<CartResponse>(cartQueryKey);
      if (previous) {
        const unit = Number.parseFloat(preview.unit_price ?? "0");
        const temp: CartItemResponse = {
          ...preview,
          id: -variantId,
          variant_id: variantId,
          quantity: String(quantity),
          line_total: (unit * quantity).toFixed(2),
        };
        queryClient.setQueryData<CartResponse>(
          cartQueryKey,
          withTotals(previous, [...previous.items.filter((i) => i.variant_id !== variantId), temp]),
        );
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(cartQueryKey, context.previous);
    },
    onSuccess: (item) => {
      // Swap the placeholder for the real server row right away so the
      // stepper becomes usable without waiting for a refetch - keeping any
      // quantity the customer already changed to while the add was in flight.
      const current = queryClient.getQueryData<CartResponse>(cartQueryKey);
      if (!current) return;
      const others = current.items.filter((i) => i.variant_id !== item.variant_id);
      const wanted = desiredQty.get(item.variant_id);
      if (wanted === undefined) {
        queryClient.setQueryData<CartResponse>(cartQueryKey, withTotals(current, [...others, item]));
      } else if (wanted > 0) {
        const unit = Number.parseFloat(item.unit_price ?? "0");
        const merged = { ...item, quantity: String(wanted), line_total: (unit * wanted).toFixed(2) };
        queryClient.setQueryData<CartResponse>(cartQueryKey, withTotals(current, [...others, merged]));
      } else {
        queryClient.setQueryData<CartResponse>(cartQueryKey, withTotals(current, others));
      }
    },
    onSettled: (_data, _err, vars) => {
      // A pending quantity change re-syncs and refetches itself afterwards;
      // refetching now would flash the server's older quantity.
      if (desiredQty.has(vars.variantId)) return;
      invalidateWhenIdle(queryClient);
    },
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
    onSettled: () => invalidateWhenIdle(queryClient),
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
    onSettled: () => invalidateWhenIdle(queryClient),
  });
}

export function useClearCart() {
  const queryClient = useQueryClient();
  const showToast = useToastStore((s) => s.show);
  return useMutation({
    mutationFn: cartApi.clear,
    onMutate: async () => {
      // Stop any in-flight cart fetch from landing after this and
      // bringing the old items back.
      await queryClient.cancelQueries({ queryKey: cartQueryKey });
      const previous = queryClient.getQueryData<CartResponse>(cartQueryKey);
      if (previous) queryClient.setQueryData<CartResponse>(cartQueryKey, withTotals(previous, []));
      return { previous };
    },
    onError: (err, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(cartQueryKey, context.previous);
      showToast(toApiError(err).message || "Couldn't clear your cart. Please try again.", "error");
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: cartQueryKey });
    },
  });
}

/** Add-to-cart / stepper convenience that resolves the right mutation
 * (add vs. update-by-item vs. remove-at-zero) from a variant id, so
 * ProductCard/ProductDetail don't need to know cart-item ids. */
export function useVariantStepper(variantId: number, preview?: CartItemPreview) {
  const queryClient = useQueryClient();
  const { data: cart } = useCart();
  const add = useAddToCart();
  const update = useUpdateCartItemQuantity();
  const remove = useRemoveCartItem();

  const item = cart?.items.find((i) => i.variant_id === variantId);
  const quantity = item ? Math.round(Number.parseFloat(item.quantity)) : 0;

  const startAdd = () => {
    const promise = add
      .mutateAsync({ variantId, quantity: 1, preview })
      .then((created) => created)
      .catch(() => null);
    pendingAdds.set(variantId, promise);
    void promise.finally(() => pendingAdds.delete(variantId));
  };

  // The add hasn't come back yet: show the new quantity now, and push it to
  // the server as soon as the add has created the real cart row.
  const changeWhilePending = (next: number) => {
    const alreadyQueued = desiredQty.has(variantId);
    desiredQty.set(variantId, next);
    queryClient.setQueryData<CartResponse>(cartQueryKey, (current) => {
      if (!current) return current;
      const others = current.items.filter((i) => i.variant_id !== variantId);
      if (next <= 0) return withTotals(current, others);
      const target = current.items.find((i) => i.variant_id === variantId);
      if (!target) return current;
      const unit = Number.parseFloat(target.unit_price ?? "0");
      return withTotals(current, [
        ...others,
        { ...target, quantity: String(next), line_total: (unit * next).toFixed(2) },
      ]);
    });
    if (alreadyQueued) return;
    void pendingAdds.get(variantId)?.then(async (created) => {
      const wanted = desiredQty.get(variantId);
      desiredQty.delete(variantId);
      try {
        if (created && wanted !== undefined) {
          if (wanted <= 0) await cartApi.removeItem(created.id);
          else if (wanted !== 1) await cartApi.updateItem(created.id, String(wanted));
        }
      } finally {
        void queryClient.invalidateQueries({ queryKey: cartQueryKey });
      }
    });
  };

  const isPendingAdd = !!item && item.id < 0;

  return {
    quantity,
    // Taps are never blocked: every change shows instantly and syncs behind.
    isMutating: false,
    add: startAdd,
    increment: () => {
      if (!item) startAdd();
      else if (isPendingAdd) changeWhilePending(quantity + 1);
      else update.mutate({ itemId: item.id, quantity: quantity + 1 });
    },
    decrement: () => {
      if (!item) return;
      if (isPendingAdd) changeWhilePending(quantity - 1);
      else if (quantity <= 1) remove.mutate(item.id);
      else update.mutate({ itemId: item.id, quantity: quantity - 1 });
    },
  };
}
