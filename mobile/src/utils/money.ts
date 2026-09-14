/**
 * Money/quantity formatting. The backend is the sole source of truth for
 * every amount here - these helpers only ever format a value the server
 * already returned, never compute a new one (see PHASE_14/18 rule: never
 * trust or compute a client-side total).
 */

const CURRENCY_SYMBOLS: Record<string, string> = {
  INR: "₹",
};

export function formatMoney(amount: string | number, currency = "INR"): string {
  const value = typeof amount === "string" ? Number.parseFloat(amount) : amount;
  const symbol = CURRENCY_SYMBOLS[currency] ?? `${currency} `;
  if (Number.isNaN(value)) return `${symbol}0`;
  const formatted = value.toLocaleString("en-IN", {
    minimumFractionDigits: value % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  });
  return `${symbol}${formatted}`;
}

/** Formats a variant's pack size, e.g. quantity="1.000" unit="KG" -> "1 kg". */
export function formatVariantSize(quantity: string, unit: string): string {
  const value = Number.parseFloat(quantity);
  const trimmed = Number.isInteger(value) ? value.toString() : value.toString();
  return `${trimmed} ${unit.toLowerCase()}`;
}

export function parseDecimal(value: string): number {
  return Number.parseFloat(value);
}
