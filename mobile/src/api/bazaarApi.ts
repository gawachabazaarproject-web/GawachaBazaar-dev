import { apiClient } from "./client";
import { BazaarStatusResponse, DeliveryQuoteResponse } from "@/types/api";

export const bazaarApi = {
  status: () => apiClient.get<BazaarStatusResponse>("/bazaar/status").then((r) => r.data),
  deliveryQuote: (addressId?: number | null) =>
    apiClient
      .get<DeliveryQuoteResponse>("/bazaar/delivery-quote", { params: addressId ? { address_id: addressId } : {} })
      .then((r) => r.data),
};
