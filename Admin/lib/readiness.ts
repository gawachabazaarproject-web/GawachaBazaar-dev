/**
 * "Is this product ready to sell?" - worked out from the real product data, the
 * same rules the storefront enforces when a customer buys:
 *
 *  - a size customers can buy (an ACTIVE size),
 *  - a price on every such size (checkout refuses a size without a valid price),
 *  - stock to sell (otherwise customers see "out of stock").
 *
 * A photo is only a suggestion: the app shows a neutral tile without one, so it
 * is listed but never counted as something that "needs attention".
 */

export type FixTarget =
  | { type: "size" }
  | { type: "price"; variantId: number }
  | { type: "stock" }
  | { type: "photo" };

export interface ReadinessProblem {
  key: string;
  /** What is wrong, in words for staff: "Price missing for 1 kg". */
  text: string;
  fix: FixTarget;
}

export interface ReadinessCheck {
  key: "info" | "photo" | "sizes" | "prices" | "stock";
  label: string;
  ok: boolean;
  /** Suggestions (the photo) are shown but not counted. */
  advisory?: boolean;
  /** Cannot be judged yet (prices before any size exists): shown neutral, not as another problem. */
  waiting?: boolean;
}

export interface Readiness {
  ready: boolean;
  checks: ReadinessCheck[];
  problems: ReadinessProblem[];
}

export interface ReadinessInput {
  name: string;
  hasCategory: boolean;
  imageCount: number;
  variants: { id: number; label: string; status: string; hasPrice: boolean }[];
  hasStock: boolean;
}

export function checkReadiness(input: ReadinessInput): Readiness {
  const sellable = input.variants.filter((v) => v.status === "ACTIVE");
  const unpriced = sellable.filter((v) => !v.hasPrice);
  const problems: ReadinessProblem[] = [];

  if (sellable.length === 0) {
    problems.push({ key: "sizes", text: "No size to sell yet", fix: { type: "size" } });
  }
  for (const v of unpriced) {
    problems.push({ key: `price:${v.id}`, text: `Price missing for ${v.label}`, fix: { type: "price", variantId: v.id } });
  }
  if (!input.hasStock) {
    problems.push({ key: "stock", text: "No stock yet", fix: { type: "stock" } });
  }

  const checks: ReadinessCheck[] = [
    { key: "info", label: "Product information", ok: input.name.trim().length > 0 && input.hasCategory },
    { key: "photo", label: "Photo", ok: input.imageCount > 0, advisory: true },
    { key: "sizes", label: "Selling sizes", ok: sellable.length > 0 },
    { key: "prices", label: "Prices", ok: sellable.length > 0 && unpriced.length === 0, waiting: sellable.length === 0 },
    { key: "stock", label: "Stock", ok: input.hasStock },
  ];
  return { ready: problems.length === 0 && checks[0].ok, checks, problems };
}

/** The same rules from the figures a list row carries (no per-size detail there). */
export function checkListReadiness(item: {
  name: string;
  primary_image_url: string | null;
  active_variant_count: number;
  priced_variant_count: number;
  total_available_stock: string;
}): Readiness {
  const missingPrices = Math.max(item.active_variant_count - item.priced_variant_count, 0);
  const problems: ReadinessProblem[] = [];
  if (item.active_variant_count === 0) problems.push({ key: "sizes", text: "No size to sell yet", fix: { type: "size" } });
  if (missingPrices > 0) {
    problems.push({
      key: "prices",
      text: missingPrices === 1 ? "A price is missing" : `${missingPrices} prices are missing`,
      fix: { type: "price", variantId: 0 },
    });
  }
  if (!(Number(item.total_available_stock) > 0)) problems.push({ key: "stock", text: "No stock yet", fix: { type: "stock" } });
  const checks: ReadinessCheck[] = [
    { key: "info", label: "Product information", ok: item.name.trim().length > 0 },
    { key: "photo", label: "Photo", ok: !!item.primary_image_url, advisory: true },
    { key: "sizes", label: "Selling sizes", ok: item.active_variant_count > 0 },
    { key: "prices", label: "Prices", ok: item.active_variant_count > 0 && missingPrices === 0, waiting: item.active_variant_count === 0 },
    { key: "stock", label: "Stock", ok: Number(item.total_available_stock) > 0 },
  ];
  return { ready: problems.length === 0, checks, problems };
}

/** Query string that sends someone to the control that fixes `target`. */
export function fixQuery(target: FixTarget): string {
  switch (target.type) {
    case "price":
      return target.variantId ? `price=${target.variantId}` : "fix=price";
    case "size":
      return "fix=size";
    case "stock":
      return "fix=stock";
    case "photo":
      return "fix=photo";
  }
}
