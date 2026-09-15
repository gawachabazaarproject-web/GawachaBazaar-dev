import { apiClient } from "./client";
import { CartItemResponse, CartResponse, OrderDetailResponse, PromotionEvaluationResponse } from "@/types/api";

export const cartApi = {
  get: () => apiClient.get<CartResponse>("/cart").then((r) => r.data),

  ensure: () => apiClient.post<CartResponse>("/cart").then((r) => r.data),

  addItem: (variantId: number, quantity: string) =>
    apiClient
      .post<CartItemResponse>("/cart/items", { variant_id: variantId, quantity })
      .then((r) => r.data),

  updateItem: (itemId: number, quantity: string) =>
    apiClient
      .patch<CartItemResponse>(`/cart/items/${itemId}`, { quantity })
      .then((r) => r.data),

  removeItem: (itemId: number) => apiClient.delete(`/cart/items/${itemId}`).then(() => undefined),

  clear: () => apiClient.delete("/cart/items").then(() => undefined),

  checkout: (addressId: number, promoCode?: string | null) =>
    apiClient
      .post<OrderDetailResponse>("/cart/checkout", {
        address_id: addressId,
        promo_code: promoCode || undefined,
      })
      .then((r) => r.data),

  evaluatePromo: (promoCode: string | null) =>
    apiClient
      .post<PromotionEvaluationResponse>("/cart/evaluate-promo", { promo_code: promoCode || undefined })
      .then((r) => r.data),
};
