import { apiClient } from "./client";
import {
  CreatePaymentPayload,
  PaymentCheckoutResponse,
  PaymentInitiationResponse,
  PaymentResponse,
  RazorpaySuccessPayload,
} from "@/types/api";

export const paymentApi = {
  create: (payload: CreatePaymentPayload) =>
    apiClient.post<PaymentInitiationResponse>("/payments", payload).then((r) => r.data),

  get: (id: number) => apiClient.get<PaymentResponse>(`/payments/${id}`).then((r) => r.data),

  retry: (id: number) =>
    apiClient.post<PaymentInitiationResponse>(`/payments/${id}/retry`).then((r) => r.data),

  verify: (id: number) =>
    apiClient.post<PaymentResponse>(`/payments/${id}/verify`).then((r) => r.data),

  checkout: (id: number) =>
    apiClient.get<PaymentCheckoutResponse>(`/payments/${id}/checkout`).then((r) => r.data),

  confirm: (id: number, payload: RazorpaySuccessPayload) =>
    apiClient.post<PaymentResponse>(`/payments/${id}/confirm`, payload).then((r) => r.data),
};
