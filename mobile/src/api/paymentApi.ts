import { apiClient } from "./client";
import { CreatePaymentPayload, PaymentInitiationResponse, PaymentResponse } from "@/types/api";

export const paymentApi = {
  create: (payload: CreatePaymentPayload) =>
    apiClient.post<PaymentInitiationResponse>("/payments", payload).then((r) => r.data),

  get: (id: number) => apiClient.get<PaymentResponse>(`/payments/${id}`).then((r) => r.data),

  retry: (id: number) =>
    apiClient.post<PaymentInitiationResponse>(`/payments/${id}/retry`).then((r) => r.data),

  verify: (id: number) =>
    apiClient.post<PaymentResponse>(`/payments/${id}/verify`).then((r) => r.data),
};
