import { apiClient } from "./client";
import { WishlistResponse } from "@/types/api";

export const wishlistApi = {
  list: () => apiClient.get<WishlistResponse>("/wishlist").then((r) => r.data),
  add: (productId: number) => apiClient.put(`/wishlist/${productId}`).then(() => undefined),
  remove: (productId: number) => apiClient.delete(`/wishlist/${productId}`).then(() => undefined),
};
