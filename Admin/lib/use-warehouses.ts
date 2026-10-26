"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { fetchLocations, Location } from "@/lib/inventory";
import { recall } from "@/lib/product-form";

/**
 * The active warehouses and the one to use by default: the only one, else the
 * one used last time, else the packing point. Screens show a picker only when
 * `locations.length > 1`, so staff are never asked what the system knows.
 */
export function useWarehouses(enabled = true) {
  const { getAccessToken } = useAuth();
  const [locations, setLocations] = useState<Location[]>([]);
  const [defaultId, setDefaultId] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const token = getAccessToken();
    if (!enabled || !token) return;
    fetchLocations(token)
      .then((all) => {
        const active = all.filter((l) => l.status === "ACTIVE");
        setLocations(active);
        const last = recall<string>("lastWarehouse");
        const pick =
          active.length === 1
            ? active[0]
            : active.find((l) => String(l.id) === last) ?? active.find((l) => l.is_packing_point);
        if (pick) setDefaultId(String(pick.id));
      })
      .catch(() => undefined)
      .finally(() => setLoaded(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  return { locations, defaultId, loaded };
}
