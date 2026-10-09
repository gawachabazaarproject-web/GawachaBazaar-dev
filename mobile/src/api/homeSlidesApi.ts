import { apiClient } from "./client";
import { HomeSlideResponse } from "@/types/api";

export const homeSlidesApi = {
  listActive: () => apiClient.get<HomeSlideResponse[]>("/home-slides").then((r) => r.data),
};
