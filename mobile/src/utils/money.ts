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

/** Display-only comparison rate, e.g. price 30, 250 g -> "₹120/kg". Not a
 * total - the server still prices every order. Returns null for sizes with
 * no per-kg/L/piece meaning (box, pack) or unusable input. */
export function formatRatePerUnit(price: string | number, quantity: string, unit: string): string | null {
  const p = typeof price === "string" ? Number.parseFloat(price) : price;
  const q = Number.parseFloat(quantity);
  if (!(p > 0) || !(q > 0)) return null;
  const perBase: Record<string, [number, string]> = {
    KG: [1, "kg"],
    G: [1000, "kg"],
    L: [1, "L"],
    ML: [1000, "L"],
    UNIT: [1, "pc"],
    DOZEN: [1 / 12, "pc"],
  };
  const entry = perBase[unit];
  if (!entry) return null;
  const rate = (p / q) * entry[0];
  return `${formatMoney(Number(rate.toFixed(2)))}/${entry[1]}`;
}

export function parseDecimal(value: string): number {
  return Number.parseFloat(value);
}
