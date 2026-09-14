import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addressApi } from "@/api";
import { CreateAddressPayload, UpdateAddressPayload } from "@/types/api";

export const addressesQueryKey = ["addresses"] as const;

export function useAddresses() {
  return useQuery({ queryKey: addressesQueryKey, queryFn: addressApi.list });
}

export function useAddress(id: number | null) {
  return useQuery({
    queryKey: ["address", id],
    queryFn: () => addressApi.get(id as number),
    enabled: id !== null,
  });
}

export function useCreateAddress() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateAddressPayload) => addressApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: addressesQueryKey }),
  });
}

export function useUpdateAddress() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: UpdateAddressPayload }) =>
      addressApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: addressesQueryKey }),
  });
}

export function useDeleteAddress() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => addressApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: addressesQueryKey }),
  });
}
