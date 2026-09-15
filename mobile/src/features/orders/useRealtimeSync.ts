import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getAccessToken, getRealtimeUrl } from "@/api/client";
import { useAuthStore } from "@/store/authStore";

/** Mirrors backend/app/core/realtime.py's message contract exactly - an
 * invalidation signal, not a full resource payload. */
interface RealtimeEvent {
  resource: "order" | "fulfillment" | "payment" | "refund";
  order_id: number;
  status: string;
  previous_status: string | null;
  occurred_at: string;
}

/** Fixed 3s reconnect delay - a customer's phone dropping in/out of
 * signal is exactly what useOrder/useOrderFulfillment's existing 30s
 * `refetchInterval` already tolerates gracefully; this just makes the
 * common case (still connected) feel instant instead of waiting out that
 * poll interval. */
const RECONNECT_DELAY_MS = 3000;

/**
 * Mounted once near the app root (see RealtimeSync in app/_layout.tsx).
 * Invalidates the affected order's react-query cache the moment its
 * status changes anywhere (admin action, delivery partner, payment
 * webhook) - `["order", id]` invalidates every sub-query keyed under it
 * (`["order", id, "fulfillment"|"payment"|"refund"]`) by react-query's
 * own default prefix-matching, so one invalidate call covers all of
 * them. This is additive to, not a replacement for, useOrders.ts's
 * existing 30s polling on order/fulfillment - that polling is what keeps
 * tracking correct through a dropped/reconnecting socket; this hook just
 * makes the common (connected) case feel live instead of waiting out
 * that interval.
 */
export function useRealtimeSync(): void {
  const status = useAuthStore((s) => s.status);
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (status !== "authenticated") {
      wsRef.current?.close();
      wsRef.current = null;
      return;
    }

    let cancelled = false;

    const connect = () => {
      const token = getAccessToken();
      if (!token || cancelled) return;

      const ws = new WebSocket(getRealtimeUrl(token));
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as RealtimeEvent;
          queryClient.invalidateQueries({ queryKey: ["order", data.order_id] });
          queryClient.invalidateQueries({ queryKey: ["orders"] });
        } catch {
          // Malformed frame - ignore rather than crash the socket handler.
        }
      };

      ws.onclose = () => {
        if (cancelled) return;
        reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [status, queryClient]);
}
