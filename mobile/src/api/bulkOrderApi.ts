import { apiClient } from "./client";
import {
  BulkCustomerProfileResponse,
  BulkOrderRequestListResponse,
  BulkOrderRequestResponse,
  CreateBulkOrderRequestPayload,
  QuoteResponse,
  UpsertBulkCustomerProfilePayload,
} from "@/types/api";

export const bulkOrderApi = {
  /** 404 (no profile yet) is expected/normal for a customer who has never
   * used wholesale ordering before - callers should treat it as "no
   * profile", not an error. */
  getProfile: () => apiClient.get<BulkCustomerProfileResponse>("/bulk-orders/profile").then((r) => r.data),

  upsertProfile: (payload: UpsertBulkCustomerProfilePayload) =>
    apiClient.put<BulkCustomerProfileResponse>("/bulk-orders/profile", payload).then((r) => r.data),

  create: (payload: CreateBulkOrderRequestPayload) =>
    apiClient.post<BulkOrderRequestResponse>("/bulk-orders/requests", payload).then((r) => r.data),

  list: (page = 1, pageSize = 20) =>
    apiClient
      .get<BulkOrderRequestListResponse>("/bulk-orders/requests", { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  get: (id: number) => apiClient.get<BulkOrderRequestResponse>(`/bulk-orders/requests/${id}`).then((r) => r.data),

  cancel: (id: number) =>
    apiClient.post<BulkOrderRequestResponse>(`/bulk-orders/requests/${id}/cancel`).then((r) => r.data),

  /** 404 (no quote yet) is expected/normal until ops has priced the
   * request - callers should treat it as "not quoted yet", not an error. */
  getQuote: (id: number) => apiClient.get<QuoteResponse>(`/bulk-orders/requests/${id}/quote`).then((r) => r.data),

  acceptQuote: (id: number) =>
    apiClient.post<BulkOrderRequestResponse>(`/bulk-orders/requests/${id}/accept`).then((r) => r.data),
};
