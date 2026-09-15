"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef } from "react";
import { useAuth } from "./auth-context";
import { API_BASE_URL } from "./api";

/**
 * Mirrors backend/app/core/realtime.py's message contract exactly - an
 * invalidation signal ("go refetch order <id>"), not a full resource
 * payload. Every page that cares re-calls its own existing fetch
 * function; nothing here tries to be a second, parallel data source.
 */
export interface RealtimeEvent {
  resource: "order" | "fulfillment" | "payment" | "refund";
  order_id: number;
  status: string;
  previous_status: string | null;
  occurred_at: string;
}

type Listener = (event: RealtimeEvent) => void;

interface RealtimeContextValue {
  subscribe: (listener: Listener) => () => void;
}

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

/** Fixed 3s reconnect delay - this is an internal ops dashboard on a
 * trusted dev/LAN network with a handful of staff users, not a public
 * client fleet, so a jittered exponential backoff would be solving a
 * problem this app doesn't have. */
const RECONNECT_DELAY_MS = 3000;

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const { status, getAccessToken } = useAuth();
  const listenersRef = useRef<Set<Listener>>(new Set());
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const subscribe = useCallback((listener: Listener) => {
    listenersRef.current.add(listener);
    return () => {
      listenersRef.current.delete(listener);
    };
  }, []);

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

      // The backend has no Authorization-header equivalent for a
      // WebSocket handshake (a browser can't set custom headers on one) -
      // see app/api/v1/realtime.py's module docstring for why the token
      // travels as a query param instead here only.
      const wsUrl = `${API_BASE_URL.replace(/^http/, "ws")}/ws/events?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as RealtimeEvent;
          listenersRef.current.forEach((listener) => listener(data));
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  return <RealtimeContext.Provider value={{ subscribe }}>{children}</RealtimeContext.Provider>;
}

/**
 * Subscribes `onEvent` for the lifetime of the calling component. The
 * subscription itself is stable (registered once) - `onEvent` is read
 * through a ref on every call so a caller never has to `useCallback` its
 * handler to avoid subscribe/unsubscribe churn on every render.
 */
export function useOrderEvents(onEvent: Listener): void {
  const ctx = useContext(RealtimeContext);
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    if (!ctx) return;
    return ctx.subscribe((event) => handlerRef.current(event));
  }, [ctx]);
}
