import { apiClient } from "./client";
import { AddressListResponse, AddressResponse, CreateAddressPayload, UpdateAddressPayload } from "@/types/api";

export const addressApi = {
  list: () => apiClient.get<AddressListResponse>("/addresses").then((r) => r.data.items),

  get: (id: number) => apiClient.get<AddressResponse>(`/addresses/${id}`).then((r) => r.data),

  create: (payload: CreateAddressPayload) =>
    apiClient.post<AddressResponse>("/addresses", payload).then((r) => r.data),

  update: (id: number, payload: UpdateAddressPayload) =>
    apiClient.patch<AddressResponse>(`/addresses/${id}`, payload).then((r) => r.data),

  remove: (id: number) => apiClient.delete(`/addresses/${id}`).then(() => undefined),
};
