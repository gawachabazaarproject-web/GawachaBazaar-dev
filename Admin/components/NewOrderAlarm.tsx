"use client";

import Link from "next/link";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useOrderEvents } from "@/lib/realtime-context";

const MUTE_STORAGE_KEY = "gawacha-admin-new-order-alarm-muted";

interface Toast {
  id: string;
  orderId: number;
  occurredAt: string;
}

/**
 * Plays an audible alarm and shows a dismissible toast the instant a new
 * order is placed, so warehouse/ops staff notice and start packing without
 * having to keep the Orders list open and polling. A brand-new order is
 * exactly the `resource: "order"` event with `previous_status: null` -
 * OrderService.checkout fires this once, right after its commit succeeds
 * (see backend/app/services/order.py) - every later transition
 * (CONFIRMED/CANCELLED/...) always carries a real previous_status and is
 * deliberately not alarmed here.
 *
 * Mounted once in the root layout (inside RealtimeProvider) so it fires
 * regardless of which Admin page staff currently have open.
 */
export function NewOrderAlarm() {
  const { status } = useAuth();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [muted, setMuted] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    try {
      setMuted(localStorage.getItem(MUTE_STORAGE_KEY) === "1");
    } catch {
      // Private-browsing/storage-blocked - default to unmuted.
    }
  }, []);

  const getAudioContext = useCallback((): AudioContext | null => {
    if (typeof window === "undefined") return null;
    const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return null;
    if (!audioCtxRef.current) {
      audioCtxRef.current = new Ctor();
    }
    return audioCtxRef.current;
  }, []);

  // Browsers suspend a freshly-created AudioContext until a real user
  // gesture occurs; priming it on the first click anywhere means the
  // alarm can actually be heard the first time it's needed, not just
  // from the second order onward.
  useEffect(() => {
    const prime = () => {
      const ctx = getAudioContext();
      if (ctx?.state === "suspended") ctx.resume().catch(() => undefined);
    };
    document.addEventListener("pointerdown", prime, { once: true });
    return () => document.removeEventListener("pointerdown", prime);
  }, [getAudioContext]);

  const playAlarm = useCallback(() => {
    const ctx = getAudioContext();
    if (!ctx) return;
    if (ctx.state === "suspended") ctx.resume().catch(() => undefined);

    const now = ctx.currentTime;
    // Two-note rising chime, repeated twice - distinct and attention-getting
    // without being a harsh siren in a shared office space.
    const notes: Array<[number, number]> = [
      [880, now],
      [1175, now + 0.16],
      [880, now + 0.55],
      [1175, now + 0.71],
    ];
    for (const [freq, start] of notes) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, start);
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.22, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.14);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(start);
      osc.stop(start + 0.16);
    }
  }, [getAudioContext]);

  useOrderEvents((event) => {
    if (event.resource !== "order" || event.previous_status !== null) return;
    setToasts((prev) => [
      ...prev,
      { id: `${event.order_id}-${event.occurred_at}`, orderId: event.order_id, occurredAt: event.occurred_at },
    ]);
    if (!muted) playAlarm();
  });

  const dismiss = (id: string) => setToasts((prev) => prev.filter((t) => t.id !== id));

  const toggleMuted = () => {
    setMuted((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(MUTE_STORAGE_KEY, next ? "1" : "0");
      } catch {
        // Ignore - mute preference just won't persist this session.
      }
      return next;
    });
  };

  if (status !== "authenticated") return null;

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="pointer-events-auto flex items-start gap-3 rounded border border-status-danger/30 bg-white px-4 py-3 shadow-lg"
        >
          <span className="mt-0.5 flex h-2.5 w-2.5 flex-shrink-0 animate-pulse rounded-full bg-status-danger" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-primary-900">New order received</p>
            <p className="text-xs text-neutral-500">Order #{toast.orderId} needs picking &amp; packing</p>
            <Link
              href={`/orders/${toast.orderId}`}
              onClick={() => dismiss(toast.id)}
              className="mt-1 inline-block text-xs font-semibold text-primary-700 hover:underline"
            >
              View order →
            </Link>
          </div>
          <button
            onClick={() => dismiss(toast.id)}
            aria-label="Dismiss"
            className="flex-shrink-0 text-neutral-400 hover:text-neutral-600"
          >
            ×
          </button>
        </div>
      ))}
      <button
        onClick={toggleMuted}
        className="pointer-events-auto ml-auto rounded-full border border-neutral-300 bg-white px-3 py-1.5 text-xs font-medium text-neutral-600 shadow hover:bg-neutral-50"
        title={muted ? "Unmute new-order alarm" : "Mute new-order alarm"}
      >
        {muted ? "🔇 Alarm off" : "🔔 Alarm on"}
      </button>
    </div>
  );
}
