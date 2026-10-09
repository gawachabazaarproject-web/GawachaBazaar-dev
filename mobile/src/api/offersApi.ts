import { apiClient } from "./client";
import { OfferResponse } from "@/types/api";

export const offersApi = {
  listLive: () => apiClient.get<OfferResponse[]>("/offers").then((r) => r.data),
};
