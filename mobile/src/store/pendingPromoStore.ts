import { create } from "zustand";

/** A promo code the shopper picked from the Home offers carousel. Checkout
 * applies it (through the normal backend evaluation) the next time it opens,
 * so "tap the offer" really means "use this offer". */
interface PendingPromoState {
  code: string | null;
  set: (code: string) => void;
  clear: () => void;
}

export const usePendingPromoStore = create<PendingPromoState>((set) => ({
  code: null,
  set: (code) => set({ code }),
  clear: () => set({ code: null }),
}));
