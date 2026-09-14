import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { bulkOrderApi } from "@/api";
import { CreateBulkOrderRequestPayload, UpsertBulkCustomerProfilePayload } from "@/types/api";

const PAGE_SIZE = 20;

/** A 404 here just means "this customer has never set up a wholesale
 * profile" - the normal case until they submit their first request. */
export function useBulkProfile() {
  return useQuery({
    queryKey: ["bulk-profile"],
    queryFn: () => bulkOrderApi.getProfile(),
    retry: false,
  });
}

export function useUpsertBulkProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UpsertBulkCustomerProfilePayload) => bulkOrderApi.upsertProfile(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["bulk-profile"] }),
  });
}

export function useBulkRequests() {
  return useInfiniteQuery({
    queryKey: ["bulk-requests"],
    queryFn: ({ pageParam }) => bulkOrderApi.list(pageParam, PAGE_SIZE),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const loaded = lastPage.page * lastPage.page_size;
      return loaded < lastPage.total ? lastPage.page + 1 : undefined;
    },
  });
}

export function useBulkRequest(id: number | null) {
  return useQuery({
    queryKey: ["bulk-request", id],
    queryFn: () => bulkOrderApi.get(id as number),
    enabled: id !== null,
    refetchInterval: 30_000, // light polling, same rationale as useOrder - status can change once ops quotes it
  });
}

export function useCreateBulkRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateBulkOrderRequestPayload) => bulkOrderApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["bulk-requests"] }),
  });
}

export function useCancelBulkRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => bulkOrderApi.cancel(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["bulk-request", id] });
      queryClient.invalidateQueries({ queryKey: ["bulk-requests"] });
    },
  });
}

/** 404 (not quoted yet) is expected/normal - callers should treat it as
 * "waiting on a quote", not an error. */
export function useBulkQuote(id: number | null) {
  return useQuery({
    queryKey: ["bulk-quote", id],
    queryFn: () => bulkOrderApi.getQuote(id as number),
    enabled: id !== null,
    retry: false,
    refetchInterval: 30_000,
  });
}

export function useAcceptBulkQuote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => bulkOrderApi.acceptQuote(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["bulk-request", id] });
      queryClient.invalidateQueries({ queryKey: ["bulk-requests"] });
      queryClient.invalidateQueries({ queryKey: ["bulk-quote", id] });
    },
  });
}
