/**
 * Money/quantity formatting. The backend is the sole source of truth for
 * every amount here - these helpers only ever format a value the server
 * already returned, never compute a new one (see PHASE_14/18 rule: never
 * trust or compute a client-side total).
 */

import { UNITS, displayUnit, formatSize } from "./units";

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
  return formatSize(quantity, unit);
}

/** Display-only comparison rate, e.g. price 30, 250 g -> "₹120/kg". Not a
 * total - the server still prices every order. Returns null for sizes with
 * no per-kg/L/piece meaning (box, pack) or unusable input. */
export function formatRatePerUnit(price: string | number, quantity: string, unit: string): string | null {
  const p = typeof price === "string" ? Number.parseFloat(price) : price;
  const q = Number.parseFloat(quantity);
  if (!(p > 0) || !(q > 0)) return null;
  const info = UNITS[unit];
  if (!info || (info.dimension !== "MASS" && info.dimension !== "VOLUME" && info.dimension !== "COUNT")) return null;
  const display = displayUnit(info.dimension);
  const label = info.dimension === "COUNT" ? "pc" : display.label;
  const rate = (p / q) * (display.factor / info.factor);
  return `${formatMoney(Number(rate.toFixed(2)))}/${label}`;
}

export function parseDecimal(value: string): number {
  return Number.parseFloat(value);
}
