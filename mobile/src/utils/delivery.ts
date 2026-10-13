import { DeliveryQuote } from "@/types/api";

/** Delivery fee as a number; 0 until a quote with a fee is available. */
export function deliveryFeeOf(quote: DeliveryQuote | undefined): number {
  return quote?.fee ? Number.parseFloat(quote.fee) : 0;
}

/** items total + delivery fee, as a decimal string. */
export function withDelivery(itemsTotal: string | null, quote: DeliveryQuote | undefined): string {
  return (Number.parseFloat(itemsTotal ?? "0") + deliveryFeeOf(quote)).toFixed(2);
}

/** "5.2 km by road" / "about 5.2 km" - what the fee was calculated on. */
export function distanceLabel(quote: DeliveryQuote | undefined): string | null {
  if (!quote || quote.needs_location || !quote.distance_km) return null;
  const km = Number.parseFloat(quote.distance_km);
  return quote.method === "estimate" ? `about ${km} km` : `${km} km by road`;
}
