import React, { useEffect } from "react";
import { useRouter, useSegments } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { addressApi } from "@/api";

/**
 * Redirect gate: authenticated + has-an-address decides which top-level
 * group the user lands in. Pure navigation side-effect, no UI of its own
 * (children always render - this only ever calls router.replace).
 *
 * First-time flow (brief §20): App -> Auth -> Address -> Home. Once a
 * customer has at least one saved address, this never sends them back to
 * onboarding, even if they later delete their only address (that's the
 * Address screen's own job to handle, not a global redirect loop).
 *
 * Lives under src/, not app/, on purpose: anything inside app/ is scanned
 * by Expo Router as a potential route, and this is a plain component, not
 * a route - keeping it out of app/ avoids the (harmless but noisy)
 * "missing default export" warning that a `_`-prefixed file under app/
 * still triggers.
 */
export function AppGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const segments = useSegments();
  const status = useAuthStore((s) => s.status);

  const inAuthGroup = segments[0] === "(auth)";
  const inOnboardingGroup = segments[0] === "(onboarding)";

  const addressesQuery = useQuery({
    queryKey: ["addresses"],
    queryFn: addressApi.list,
    enabled: status === "authenticated",
    staleTime: 60_000,
  });

  useEffect(() => {
    if (status === "restoring") return;

    if (status === "unauthenticated") {
      if (!inAuthGroup) router.replace("/(auth)/login");
      return;
    }

    // authenticated
    if (addressesQuery.isLoading) return;
    const hasAddress = (addressesQuery.data?.length ?? 0) > 0;

    if (!hasAddress && !inOnboardingGroup) {
      router.replace("/(onboarding)/address");
      return;
    }
    if ((inAuthGroup || inOnboardingGroup) && hasAddress) {
      router.replace("/(tabs)");
    }
  }, [status, inAuthGroup, inOnboardingGroup, addressesQuery.data, addressesQuery.isLoading, router]);

  return <>{children}</>;
}
