/**
 * Helpers for the Add product form: web-address/SKU generation, parsing a
 * typed size ("250g", "1 kg", "12 pcs"), per-kg price pre-fill, and the
 * operator's remembered choices (browser storage; only a convenience).
 */

/** "tomato", "red-onion". A name without Latin letters or digits (e.g. Marathi)
 * has no readable web address, so a short unique one is made instead. */
export function slugify(value: string): string {
  const slug = value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
  return slug || `product-${Date.now().toString(36)}`;
}

/** Same as `slugify` but "" for text with nothing to slug (used for sizes). */
export function slugPart(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

const UNIT_WORDS: Record<string, string> = {
  kg: "KG", kgs: "KG", kilo: "KG", kilos: "KG",
  g: "G", gm: "G", gms: "G", gram: "G", grams: "G",
  l: "L", ltr: "L", litre: "L", litres: "L", liter: "L", liters: "L",
  ml: "ML",
  pc: "UNIT", pcs: "UNIT", piece: "UNIT", pieces: "UNIT", unit: "UNIT", units: "UNIT",
  dozen: "DOZEN", doz: "DOZEN",
  box: "BOX", pack: "PACK",
};

export interface ParsedSize {
  quantity: string;
  unit: string;
}

/** "250g" / "1 kg" / "12 pcs" -> { quantity: "250", unit: "G" }; null when it can't be read. */
export function parseSize(text: string): ParsedSize | null {
  const match = text.trim().match(/^(\d+(?:\.\d+)?)\s*([a-z]+)$/i);
  if (!match) return null;
  const quantity = Number(match[1]);
  const unit = UNIT_WORDS[match[2].toLowerCase()];
  if (!(quantity > 0) || !unit) return null;
  return { quantity: String(quantity), unit };
}

/** Sizes offered as one-tap chips. */
export const SIZE_CHIPS = ["250 g", "500 g", "1 kg", "2 kg", "5 kg", "1 L", "6 pc", "1 dozen"];

// unit -> [family, size of one unit in the family's base unit (g / ml / pieces)]
const FAMILY: Record<string, [string, number]> = {
  KG: ["MASS", 1000], G: ["MASS", 1], L: ["VOLUME", 1000], ML: ["VOLUME", 1],
  UNIT: ["COUNT", 1], DOZEN: ["COUNT", 12],
};

export function unitFamily(unit: string): string | null {
  return FAMILY[unit]?.[0] ?? null;
}

/** Label of the "rate" a price can be entered as, per family. */
export const RATE_LABEL: Record<string, string> = { MASS: "kg", VOLUME: "L", COUNT: "piece" };

/** Pack price for a rate per kg / L / piece, rounded to the nearest rupee.
 * Only a pre-fill: the operator can change every price before saving. */
export function priceFromRate(rate: number, quantity: string, unit: string): string {
  const entry = FAMILY[unit];
  if (!entry || !(rate > 0)) return "";
  const perBaseUnit = entry[0] === "COUNT" ? rate : rate / 1000; // rate per kg -> per g
  const price = Math.max(1, Math.round(perBaseUnit * Number(quantity) * entry[1]));
  return String(price);
}

export const STATUS_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  ACTIVE: "Live",
  INACTIVE: "Hidden",
  ARCHIVED: "Archived",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

const PREFIX = "gb.admin.";

export function remember(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    /* storage unavailable (private window): remembering is optional */
  }
}

export function recall<T>(key: string): T | null {
  try {
    const raw = window.localStorage.getItem(PREFIX + key);
    return raw === null ? null : (JSON.parse(raw) as T);
  } catch {
    return null;
  }
}
