import { create } from "zustand";

export type ToastTone = "default" | "error" | "success";

interface ToastState {
  message: string | null;
  tone: ToastTone;
  show: (message: string, tone?: ToastTone) => void;
  hide: () => void;
}

/** Minimal global toast for transient, non-blocking feedback (mutation
 * errors, "removed from cart", etc.) - not a notification center, just
 * one message at a time. */
export const useToastStore = create<ToastState>((set) => ({
  message: null,
  tone: "default",
  show: (message, tone = "default") => set({ message, tone }),
  hide: () => set({ message: null }),
}));
