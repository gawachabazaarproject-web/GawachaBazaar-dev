import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toApiError, wishlistApi } from "@/api";
import { useToastStore } from "@/store/toastStore";
import { WishlistResponse } from "@/types/api";

export const wishlistQueryKey = ["wishlist"] as const;

export function useWishlist() {
  return useQuery({ queryKey: wishlistQueryKey, queryFn: wishlistApi.list });
}

/** Heart state + optimistic toggle for one product. */
export function useWishlistToggle(productId: number) {
  const queryClient = useQueryClient();
  const showToast = useToastStore((s) => s.show);
  const { data } = useWishlist();
  const liked = data?.product_ids.includes(productId) ?? false;

  const mutation = useMutation({
    mutationFn: (next: boolean) => (next ? wishlistApi.add(productId) : wishlistApi.remove(productId)),
    onMutate: async (next) => {
      await queryClient.cancelQueries({ queryKey: wishlistQueryKey });
      const previous = queryClient.getQueryData<WishlistResponse>(wishlistQueryKey);
      if (previous) {
        const ids = next
          ? [productId, ...previous.product_ids.filter((i) => i !== productId)]
          : previous.product_ids.filter((i) => i !== productId);
        queryClient.setQueryData<WishlistResponse>(wishlistQueryKey, {
          items: next ? previous.items : previous.items.filter((i) => i.id !== productId),
          product_ids: ids,
        });
      }
      return { previous };
    },
    onError: (err, _next, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(wishlistQueryKey, ctx.previous);
      showToast(toApiError(err).message, "error");
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: wishlistQueryKey }),
  });

  return { liked, toggle: () => mutation.mutate(!liked) };
}
