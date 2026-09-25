import { apiClient } from "./client";
import { AdResponse } from "@/types/api";

export const adsApi = {
  listActive: () => apiClient.get<AdResponse[]>("/ads").then((r) => r.data),
};
