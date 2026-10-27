/**
 * The ONE place unit conversion lives on the client. A byte-identical copy is
 * kept at mobile/src/utils/units.ts, and backend/tests/test_units_parity.py fails
 * if either copy drifts from backend/app/services/units.py.
 *
 * Inventory is accounted in integer BASE units: MASS = grams, VOLUME = ml,
 * COUNT = pieces (BOX / PACK / CRATE are their own unit, one base unit each).
 * A size ("250 g", "1 kg", "1 dozen") is only a conversion factor; packs are a
 * sale/display quantity derived from base units. Clients only DISPLAY and
 * PREVIEW - the server owns every stored quantity.
 */

export type Dimension = "MASS" | "VOLUME" | "COUNT" | "BOX" | "PACK" | "CRATE";

export interface UnitInfo {
  dimension: Dimension;
  /** Base units in 1 of this unit. */
  factor: number;
  /** Label of the dimension's base unit. */
  baseLabel: string;
  /** How the unit is written next to a number ("1 kg", "6 pc"). */
  label: string;
  /** How it is named in a unit picker ("pieces"). */
  inputLabel: string;
}

export const UNITS: Record<string, UnitInfo> = {
  KG: { dimension: "MASS", factor: 1000, baseLabel: "g", label: "kg", inputLabel: "kg" },
  G: { dimension: "MASS", factor: 1, baseLabel: "g", label: "g", inputLabel: "g" },
  L: { dimension: "VOLUME", factor: 1000, baseLabel: "ml", label: "L", inputLabel: "L" },
  ML: { dimension: "VOLUME", factor: 1, baseLabel: "ml", label: "ml", inputLabel: "ml" },
  UNIT: { dimension: "COUNT", factor: 1, baseLabel: "pc", label: "pc", inputLabel: "pieces" },
  DOZEN: { dimension: "COUNT", factor: 12, baseLabel: "pc", label: "dozen", inputLabel: "dozen" },
  BOX: { dimension: "BOX", factor: 1, baseLabel: "box", label: "box", inputLabel: "box" },
  PACK: { dimension: "PACK", factor: 1, baseLabel: "pack", label: "pack", inputLabel: "pack" },
  CRATE: { dimension: "CRATE", factor: 1, baseLabel: "crate", label: "crate", inputLabel: "crate" },
};

/** Dimensions whose units convert into each other. */
export const CONVERTIBLE: Dimension[] = ["MASS", "VOLUME", "COUNT"];

/** Units stock can be typed in, per dimension (larger unit first). */
export const AMOUNT_UNITS_BY_DIMENSION: Record<string, string[]> = {
  MASS: ["KG", "G"],
  VOLUME: ["L", "ML"],
  COUNT: ["UNIT", "DOZEN"],
};

export function unitInfo(unit: string): UnitInfo | null {
  return UNITS[unit] ?? null;
}

export function dimensionOf(unit: string): Dimension | null {
  return UNITS[unit]?.dimension ?? null;
}

export function sameDimension(a: string, b: string): boolean {
  const da = dimensionOf(a);
  return da !== null && da === dimensionOf(b);
}

/** `amount` of `unit` as an exact whole number of base units, or null when it is
 * not whole (0.0005 kg = half a gram) or the unit is unknown. Never rounds. */
export function toBase(amount: number | string, unit: string): number | null {
  const info = UNITS[unit];
  const n = Number(amount);
  if (!info || !Number.isFinite(n)) return null;
  const scaled = n * info.factor;
  const whole = Math.round(scaled);
  return Math.abs(scaled - whole) < 1e-6 ? whole : null;
}

/** Base units in ONE pack of a size (quantity x unit), or null if not whole / not positive. */
export function sizeBase(quantity: number | string, unit: string): number | null {
  const base = toBase(quantity, unit);
  return base !== null && base > 0 ? base : null;
}

/** Whole packs a base quantity can sell (floor). Integer arithmetic only. */
export function packsFor(base: number, size: number): number {
  return size > 0 && base > 0 ? Math.floor(base / size) : 0;
}

/** Base units as an amount of `unit` (display only): 2500 g, "KG" -> 2.5. */
export function baseToAmount(base: number, unit: string): number {
  return base / (UNITS[unit]?.factor ?? 1);
}

/** Convert an amount between two units of the SAME dimension (null otherwise). */
export function convert(amount: number, from: string, to: string): number | null {
  if (!sameDimension(from, to)) return null;
  return (amount * UNITS[from].factor) / UNITS[to].factor;
}

/** The unit people read a dimension in: kg / L / pcs. */
export function displayUnit(dimension: string): { label: string; factor: number } {
  if (dimension === "MASS") return { label: "kg", factor: 1000 };
  if (dimension === "VOLUME") return { label: "L", factor: 1000 };
  if (dimension === "COUNT") return { label: "pcs", factor: 1 };
  return { label: dimension.toLowerCase(), factor: 1 };
}

const trim = (n: number, places = 3) => String(Number(n.toFixed(places)));

/** "68.999 kg", "12 pcs", "2.5 L" for a base quantity of a dimension. */
export function amountText(base: number, dimension: string): string {
  const { label, factor } = displayUnit(dimension);
  return `${trim(base / factor)} ${label}`;
}

/** Size name: "250 g", "1 kg", "6 pc", "1 dozen" (never "6 unit"). */
export function formatSize(quantity: number | string, unit: string): string {
  return `${trim(Number(quantity))} ${UNITS[unit]?.label ?? unit.toLowerCase()}`;
}

/** What a number of packs adds up to, e.g. 24 pieces, "2 dozen (24 pieces)", "1.5 kg". */
export function packTotalText(packs: number | string, quantity: number | string, unit: string): string | null {
  const info = UNITS[unit];
  if (!info) return null;
  const total = Number(packs) * Number(quantity);
  const base = total * info.factor;
  if (info.dimension === "MASS" || info.dimension === "VOLUME") {
    const { label, factor } = displayUnit(info.dimension);
    const small = info.dimension === "MASS" ? "g" : "ml";
    return base >= factor ? `${trim(base / factor)} ${label}` : `${trim(base)} ${small}`;
  }
  if (info.dimension === "COUNT") {
    const pieces = `${trim(base)} ${base === 1 ? "piece" : "pieces"}`;
    return unit === "DOZEN" ? `${trim(total)} dozen (${pieces})` : pieces;
  }
  return `${trim(total)} ${info.label}`;
}
