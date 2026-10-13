import { apiClient } from "./client";
import {
  CreatePaymentPayload,
  OnlineCheckoutCompleteResponse,
  OnlineCheckoutResponse,
  PaymentCheckoutResponse,
  PaymentInitiationResponse,
  PaymentResponse,
  RazorpaySuccessPayload,
} from "@/types/api";

export const paymentApi = {
  /** Pay-first online checkout: prices the cart and returns the Razorpay
   * order to open. Creates no order. */
  startOnline: (addressId: number, promoCode?: string | null) =>
    apiClient
      .post<OnlineCheckoutResponse>("/payments/online/start", { address_id: addressId, promo_code: promoCode ?? null })
      .then((r) => r.data),
  /** After Razorpay reports success: the backend verifies, then places the order. */
  confirmOnline: (sessionId: number, payload: RazorpaySuccessPayload) =>
    apiClient
      .post<OnlineCheckoutCompleteResponse>(`/payments/online/${sessionId}/confirm`, payload)
      .then((r) => r.data),
  /** Ask the backend to re-check a checkout with Razorpay (no client proof needed). */
  verifyOnline: (sessionId: number) =>
    apiClient.post<OnlineCheckoutCompleteResponse>(`/payments/online/${sessionId}/verify`).then((r) => r.data),
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
