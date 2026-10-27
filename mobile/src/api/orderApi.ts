import { apiClient } from "./client";
import {
  CancelOrderPayload,
  CustomerFulfillmentResponse,
  InventoryReservationResponse,
  OrderDetailResponse,
  OrderListResponse,
  PaymentResponse,
  RefundResponse,
} from "@/types/api";

/** COD delivery code, owner only. `otp` is present only while status is ACTIVE. */
export interface DeliveryOtp {
  required: boolean;
  status: "NOT_REQUIRED" | "WAITING" | "ACTIVE" | "EXPIRED" | "LOCKED" | "VERIFIED" | "COMPLETED" | "CANCELLED";
  otp: string | null;
  expires_at: string | null;
  seconds_left: number | null;
}

export const orderApi = {
  list: (page = 1, pageSize = 20) =>
    apiClient
      .get<OrderListResponse>("/orders", { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  get: (id: number) => apiClient.get<OrderDetailResponse>(`/orders/${id}`).then((r) => r.data),

  cancel: (id: number, payload: CancelOrderPayload) =>
    apiClient.post<OrderDetailResponse>(`/orders/${id}/cancel`, payload).then((r) => r.data),

  getPayment: (id: number) =>
    apiClient.get<PaymentResponse>(`/orders/${id}/payment`).then((r) => r.data),

  getFulfillment: (id: number) =>
    apiClient.get<CustomerFulfillmentResponse>(`/orders/${id}/fulfillment`).then((r) => r.data),

  getDeliveryOtp: (id: number) =>
    apiClient.get<DeliveryOtp>(`/orders/${id}/delivery-otp`).then((r) => r.data),

  getReservation: (id: number) =>
    apiClient.get<InventoryReservationResponse>(`/orders/${id}/reservation`).then((r) => r.data),

  /** 404 (no refund exists) is expected/normal for most orders - callers
   * should treat it as "no refund", not an error. */
  getRefund: (id: number) =>
    apiClient.get<RefundResponse>(`/orders/${id}/refund`).then((r) => r.data),
};
