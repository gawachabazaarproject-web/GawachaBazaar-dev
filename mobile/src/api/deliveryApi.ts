import { apiClient } from "./client";
import { GeocodeCandidate } from "@/types/api";

export const deliveryApi = {
  /** Address search (Nominatim via our backend). Call from a Search button, not per keystroke. */
  geocode: (query: string) =>
    apiClient.post<{ items: GeocodeCandidate[] }>("/delivery/geocode", { query }).then((r) => r.data.items),
};
