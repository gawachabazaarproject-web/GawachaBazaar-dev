import { useQuery } from "@tanstack/react-query";
import { offersApi } from "@/api";

/** Live offers the admin chose to advertise (Promotions -> "Show in app carousel"). */
export function useOffers() {
  return useQuery({
    queryKey: ["offers"],
    queryFn: offersApi.listLive,
    staleTime: 60_000,
  });
}
