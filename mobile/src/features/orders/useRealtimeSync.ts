import { useEffect, useRef } from "react";
import { AppState } from "react-native";
import { useQueryClient } from "@tanstack/react-query";
import { fetchAccessToken, getRealtimeUrl } from "@/api/client";
import { useAuthStore } from "@/store/authStore";

/** Mirrors backend/app/core/realtime.py's message contract exactly - an
 * invalidation signal, not a full resource payload. */
interface RealtimeEvent {
  type?: "pong";
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
/** Client->server ping cadence. Hosts' proxies (Render) silently drop idle
 * WebSockets, and a phone that was backgrounded often never fires onclose -
 * so the socket looks open while delivering nothing. The server answers each
 * ping; no frame at all for DEAD_AFTER_MS means the socket is dead. */
const PING_MS = 20_000;
const DEAD_AFTER_MS = 50_000;

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
    let lastSeen = Date.now();

    const refreshOrders = () => {
      void queryClient.invalidateQueries({ queryKey: ["order"] });
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
    };

    const connect = async () => {
      // Fresh Firebase ID token per (re)connect - a cached one may have
      // expired while the socket was up.
      const token = await fetchAccessToken().catch(() => null);
      if (!token || cancelled) return;

      const ws = new WebSocket(getRealtimeUrl(token));
      wsRef.current = ws;
      lastSeen = Date.now();

      // Anything that happened while we were disconnected is missed, so
      // resync once the socket is (re)established.
      ws.onopen = () => {
        lastSeen = Date.now();
        refreshOrders();
      };

      ws.onmessage = (event) => {
        lastSeen = Date.now();
        try {
          const data = JSON.parse(event.data) as RealtimeEvent;
          if (data.type === "pong") return;
          queryClient.invalidateQueries({ queryKey: ["order", data.order_id] });
          queryClient.invalidateQueries({ queryKey: ["orders"] });
        } catch {
          // Malformed frame - ignore rather than crash the socket handler.
        }
      };

      ws.onclose = () => {
        if (cancelled) return;
        reconnectTimerRef.current = setTimeout(() => void connect(), RECONNECT_DELAY_MS);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    void connect();

    // Heartbeat + dead-socket watchdog.
    const heartbeat = setInterval(() => {
      const ws = wsRef.current;
      if (!ws) return;
      if (Date.now() - lastSeen > DEAD_AFTER_MS) {
        ws.close(); // onclose schedules the reconnect
        return;
      }
      if (ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, PING_MS);

    // Back from the background: the socket may be dead and updates were
    // missed - reconnect right away and refetch.
    const appStateSub = AppState.addEventListener("change", (next) => {
      if (next !== "active") return;
      refreshOrders();
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
        void connect();
      } else {
        ws.send("ping");
      }
    });

    return () => {
      cancelled = true;
      clearInterval(heartbeat);
      appStateSub.remove();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [status, queryClient]);
}
