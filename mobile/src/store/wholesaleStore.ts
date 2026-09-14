import { create } from "zustand";
import { RequestUnit } from "@/types/api";

export type ShoppingMode = "regular" | "wholesale";

export interface DraftBulkItem {
  productId: number;
  productName: string;
  imageUrl: string | null;
  quantity: string;
  unit: RequestUnit;
}

interface WholesaleState {
  /** Which experience Home/Search/Categories currently render - purely a
   * client-side view switch, never sent to the backend. */
  mode: ShoppingMode;
  setMode: (mode: ShoppingMode) => void;

  /** The wholesale equivalent of a cart: items the customer is building
   * up into a bulk order REQUEST (never an Order, never priced client-side
   * - see bulk_order.py). Submitting clears this and creates a real
   * BulkOrderRequest via the API. */
  draftItems: DraftBulkItem[];
  addOrUpdateItem: (item: DraftBulkItem) => void;
  removeItem: (productId: number) => void;
  clearDraft: () => void;

  notes: string;
  setNotes: (notes: string) => void;
  addressId: number | null;
  setAddressId: (id: number | null) => void;
}

export const useWholesaleStore = create<WholesaleState>((set, get) => ({
  mode: "regular",
  setMode: (mode) => set({ mode }),

  draftItems: [],
  addOrUpdateItem: (item) => {
    const existing = get().draftItems;
    const index = existing.findIndex((i) => i.productId === item.productId);
    if (index === -1) {
      set({ draftItems: [...existing, item] });
    } else {
      const next = [...existing];
      next[index] = item;
      set({ draftItems: next });
    }
  },
  removeItem: (productId) => set({ draftItems: get().draftItems.filter((i) => i.productId !== productId) }),
  clearDraft: () => set({ draftItems: [], notes: "", addressId: null }),

  notes: "",
  setNotes: (notes) => set({ notes }),
  addressId: null,
  setAddressId: (addressId) => set({ addressId }),
}));
