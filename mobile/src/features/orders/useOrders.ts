import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { orderApi } from "@/api";
import { CancelOrderPayload } from "@/types/api";

const PAGE_SIZE = 20;

export function useOrders() {
  return useInfiniteQuery({
    queryKey: ["orders"],
    queryFn: ({ pageParam }) => orderApi.list(pageParam, PAGE_SIZE),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const loaded = lastPage.page * lastPage.page_size;
      return loaded < lastPage.total ? lastPage.page + 1 : undefined;
    },
  });
}

export function useOrder(id: number | null) {
  return useQuery({
    queryKey: ["order", id],
    queryFn: () => orderApi.get(id as number),
    enabled: id !== null,
    refetchInterval: 30_000, // light polling so tracking feels "live" without pretending to have push/GPS
  });
}

export function useOrderFulfillment(id: number | null) {
  return useQuery({
    queryKey: ["order", id, "fulfillment"],
    queryFn: () => orderApi.getFulfillment(id as number),
    enabled: id !== null,
    refetchInterval: 30_000,
  });
}

export function useOrderPayment(id: number | null) {
  return useQuery({
    queryKey: ["order", id, "payment"],
    queryFn: () => orderApi.getPayment(id as number),
    enabled: id !== null,
  });
}

/** A 404 here just means "no refund exists for this order" - the normal
 * case for the vast majority of orders, never surfaced as an error. */
export function useOrderRefund(id: number | null) {
  return useQuery({
    queryKey: ["order", id, "refund"],
    queryFn: () => orderApi.getRefund(id as number),
    enabled: id !== null,
    retry: false,
  });
}

export function useCancelOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: CancelOrderPayload }) =>
      orderApi.cancel(id, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["order", variables.id] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}
