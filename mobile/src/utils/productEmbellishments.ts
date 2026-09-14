/**
 * Illustrative presentation layer, explicitly authorized as mock content
 * (not backed by any real backend field) - Marathi names, farm/origin
 * labels, ETA flags, freshness story badges, and MRP-for-discount-display.
 * Keyed by product slug, applied ON TOP of real product/price/cart data;
 * never used to fabricate a network response or change what Add-to-cart
 * actually does.
 *
 * `mrp` is a fabricated "was" price used only to render a strikethrough
 * discount, exactly like `PriceTag`'s existing (real-data-only) mrp slot
 * - the backend has no MRP field, so this is deliberately separate from
 * anything sourced from the API.
 */
export interface ProductEmbellishment {
  marathiName?: string;
  origin?: string;
  mrp?: string;
  /** Grid/search discount-style badge, e.g. "25% OFF", "MORNING HARVEST". */
  badge?: string;
  /** Illustrative delivery ETA flag shown on search result cards. */
  eta?: string;
  /** Freshness/story badge shown on cart rows, e.g. "TODAY", "PURE A2". */
  cartBadge?: string;
}

export const PRODUCT_EMBELLISHMENTS: Record<string, ProductEmbellishment> = {
  "ripe-tomatoes": {
    marathiName: "टोमॅटो",
    origin: "Katol Farm",
    mrp: "46.00",
    badge: "25% OFF",
    eta: "22 MINS",
    cartBadge: "TODAY",
  },
  "fresh-fenugreek": { marathiName: "मेथी", origin: "Saoner", mrp: "25.00", badge: "SAVE ₹7", eta: "25 MINS", cartBadge: "HYDRO FRESH" },
  "green-peas": { marathiName: "मटर", origin: "Kalmeshwar", mrp: "60.00", badge: "25% OFF", eta: "28 MINS" },
  "chillies-coriander": { marathiName: "मिरची व कोथिंबीर", origin: "Bhandara", badge: "DAILY MUST", eta: "25 MINS" },
  "fresh-oranges": { marathiName: "संत्री", origin: "Katol & Saoner Orchards", mrp: "110.00", eta: "30 MINS" },
  "toned-milk": { marathiName: "दूध", origin: "Umred Desi Goshala", badge: "A2 · CHILLED", eta: "20 MINS", cartBadge: "PURE A2" },
  "toor-dal": { marathiName: "तूर डाळ", origin: "Wardha Organic Cluster", eta: "35 MINS" },
  "red-onions": { marathiName: "कांदा", origin: "Wardha Local", eta: "24 MINS" },
  "potatoes": { marathiName: "बटाटा", origin: "Saoner Farm", eta: "24 MINS", cartBadge: "VIDARBHA PICK" },
  "fresh-bananas": { marathiName: "केळी", origin: "Umred Farm", eta: "22 MINS" },
  "basmati-rice": { origin: "Wardha Organic Cluster", eta: "35 MINS" },
  "wheat-atta": { origin: "Wardha Organic Cluster", eta: "35 MINS" },
  "brown-bread": { origin: "Nagpur Bakehouse", eta: "20 MINS" },
  "curd": { marathiName: "दही", origin: "Umred Desi Goshala", eta: "20 MINS" },
  "paneer": { origin: "Umred Desi Goshala", eta: "20 MINS" },
  "fresh-coriander": { marathiName: "कोथिंबीर", origin: "Bhandara", eta: "22 MINS" },
  "green-chillies": { marathiName: "मिरची", origin: "Bhiwapur", eta: "22 MINS" },
  "fresh-lemons": { marathiName: "लिंबू", origin: "Saoner", eta: "22 MINS" },
  "curry-leaves": { marathiName: "कढीपत्ता", origin: "Saoner", eta: "22 MINS" },
};

export function getEmbellishment(slug: string): ProductEmbellishment {
  return PRODUCT_EMBELLISHMENTS[slug] ?? {};
}
