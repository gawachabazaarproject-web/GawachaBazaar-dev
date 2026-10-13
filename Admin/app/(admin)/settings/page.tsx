"use client";

import React, { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { useAuth } from "@/lib/auth-context";
import {
  fetchLocations,
  InventoryApiError,
  Location,
  setPackingPoint,
  updateLocationCoordinates,
} from "@/lib/inventory";

/** Accepts "21.1458, 79.0882" - what Google Maps copies on right-click. */
function parseCoordinates(text: string): { lat: number; lon: number } | null {
  const m = text.trim().match(/^(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)$/);
  if (!m) return null;
  const lat = Number(m[1]);
  const lon = Number(m[2]);
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
  return { lat, lon };
}

export default function SettingsPage() {
  const { getAccessToken } = useAuth();
  const [locations, setLocations] = useState<Location[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const token = getAccessToken();
    if (!token) return;
    fetchLocations(token)
      .then((items) => {
        setLocations(items.filter((l) => l.status === "ACTIVE"));
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Unable to load locations."));
  }, [getAccessToken]);

  useEffect(load, [load]);

  const current = locations?.find((l) => l.is_packing_point);

  return (
    <div>
      <PageHeader
        eyebrow="Platform"
        title="Settings"
        description="Delivery distance is measured by road from the packing point you choose here to each customer's address."
      />

      <h2 className="mb-2 font-display text-lg font-semibold text-primary-900">Packing point</h2>
      {error ? (
        <p className="rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">
          {error}{" "}
          <button onClick={load} className="font-semibold underline">
            Retry
          </button>
        </p>
      ) : locations === null ? (
        <p className="text-sm text-neutral-500">Loading...</p>
      ) : locations.length === 0 ? (
        <EmptyState
          icon="settings"
          title="No warehouses yet"
          message="Add a warehouse from the Inventory page first, then come back to pick it as the packing point."
        />
      ) : (
        <>
          <p
            className={`mb-4 rounded border px-3 py-2 text-sm ${
              current ? "border-primary-200 bg-primary-50 text-primary-900" : "border-neutral-300 bg-neutral-50 text-neutral-800"
            }`}
          >
            {current
              ? `Delivery is priced from "${current.name}" (${current.city}).`
              : "No packing point chosen - delivery fees use only the base fee (or the server's fallback location)."}
          </p>
          <div className="space-y-3">
            {locations.map((loc) => (
              <LocationRow key={loc.id} loc={loc} onChanged={load} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function LocationRow({ loc, onChanged }: { loc: Location; onChanged: () => void }) {
  const { getAccessToken } = useAuth();
  const initial = loc.latitude != null && loc.longitude != null ? `${loc.latitude}, ${loc.longitude}` : "";
  const [coords, setCoords] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => setCoords(initial), [initial]);

  const parsed = parseCoordinates(coords);
  const dirty = coords.trim() !== initial;
  const hasSaved = loc.latitude != null && loc.longitude != null;

  const run = async (fn: (token: string) => Promise<unknown>) => {
    const token = getAccessToken();
    if (!token) return;
    setBusy(true);
    setMsg(null);
    try {
      await fn(token);
      onChanged();
    } catch (e) {
      setMsg(e instanceof InventoryApiError ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setMsg("This browser cannot share its location.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) => setCoords(`${p.coords.latitude.toFixed(6)}, ${p.coords.longitude.toFixed(6)}`),
      () => setMsg("Location permission was denied."),
    );
  };

  return (
    <div className={`rounded border bg-white p-4 ${loc.is_packing_point ? "border-primary-700" : "border-neutral-200"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-primary-900">
            {loc.name} <span className="font-normal text-neutral-500">- {loc.code}</span>
            {loc.is_packing_point && (
              <span className="ml-2 rounded bg-primary-800 px-2 py-0.5 text-xs font-semibold text-white">Packing point</span>
            )}
          </p>
          <p className="text-sm text-neutral-600">{[loc.address_line_1, loc.city].filter(Boolean).join(", ")}</p>
        </div>
        {!loc.is_packing_point && (
          <button
            disabled={busy || !hasSaved || dirty}
            onClick={() => run((t) => setPackingPoint(t, loc.id))}
            title={!hasSaved ? "Save map coordinates first" : dirty ? "Save your coordinate changes first" : undefined}
            className="rounded bg-primary-800 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40"
          >
            Use as packing point
          </button>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          value={coords}
          onChange={(e) => setCoords(e.target.value)}
          placeholder="Latitude, longitude e.g. 21.1458, 79.0882"
          className="w-full max-w-sm rounded border border-neutral-300 px-3 py-2 text-sm"
        />
        <button
          disabled={busy || !dirty || !parsed}
          onClick={() => parsed && run((t) => updateLocationCoordinates(t, loc.id, parsed.lat, parsed.lon))}
          className="rounded border border-primary-800 px-3 py-2 text-sm font-semibold text-primary-800 disabled:opacity-40"
        >
          Save location
        </button>
        <button onClick={useMyLocation} className="rounded border border-neutral-300 px-3 py-2 text-sm text-neutral-700">
          Use my current location
        </button>
        {parsed && (
          <a
            href={`https://www.google.com/maps?q=${parsed.lat},${parsed.lon}`}
            target="_blank"
            rel="noreferrer"
            className="text-sm font-medium text-primary-800 underline"
          >
            Check on map
          </a>
        )}
      </div>
      {coords.trim() && !parsed && (
        <p className="mt-1 text-xs text-status-danger">
          Enter as latitude, longitude. In Google Maps, right-click the spot and click the numbers to copy them.
        </p>
      )}
      {msg && <p className="mt-2 text-sm text-status-danger">{msg}</p>}
    </div>
  );
}
