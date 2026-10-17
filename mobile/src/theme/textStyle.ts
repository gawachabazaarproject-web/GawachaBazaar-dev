import type { TextStyle } from "react-native";

/**
 * Safety net applied to every <Text> (see components/Text.tsx) so text renders
 * the same on small / old Android phones as on a new one. No layout change is
 * intended - each rule fixes a way Android draws these custom fonts badly:
 *
 * 1. fontWeight + custom fontFamily. Our fonts ship one file per weight (the
 *    weight is part of the family name, e.g. PlusJakartaSans_700Bold). Adding
 *    fontWeight on top makes Android synthesize an extra bold over an already
 *    bold face: glyphs look smeared / uneven / too heavy. We drop fontWeight
 *    and pick the family file for that weight instead, so the intended weight
 *    is kept but drawn from the real font file.
 * 2. Line box shorter than the font's glyphs. Android clips glyphs to the
 *    line box, so tall marks are "chipped": Marathi / Devanagari (Baloo 2)
 *    needs ~1.5x line height, display serif (Bodoni / Instrument) ~1.1x.
 *    We only ever raise a too-small lineHeight, never lower one.
 * 3. includeFontPadding (Android only, default true) adds uneven extra space
 *    above/below custom-font text, which shows up as vertical misalignment in
 *    chips, buttons and rows. Switched off for text.
 */

type Weight = 400 | 500 | 600 | 700 | 800;

/** Weights that exist as loaded font files (see useFonts in app/_layout.tsx). */
const FAMILY_FILES: Record<string, Partial<Record<Weight, string>>> = {
  PlusJakartaSans: {
    400: "PlusJakartaSans_400Regular",
    500: "PlusJakartaSans_500Medium",
    600: "PlusJakartaSans_600SemiBold",
    700: "PlusJakartaSans_700Bold",
    800: "PlusJakartaSans_800ExtraBold",
  },
  BodoniModa: {
    400: "BodoniModa_400Regular",
    500: "BodoniModa_500Medium",
    600: "BodoniModa_600SemiBold",
    700: "BodoniModa_700Bold",
    800: "BodoniModa_800ExtraBold",
  },
  Lora: { 600: "Lora_600SemiBold", 700: "Lora_700Bold" },
  Baloo2: { 500: "Baloo2_500Medium", 600: "Baloo2_600SemiBold", 700: "Baloo2_700Bold" },
};

const DEVANAGARI_MIN_LINE_RATIO = 1.5;
const DISPLAY_MIN_LINE_RATIO = 1.1;

function toWeight(value: TextStyle["fontWeight"]): number {
  if (value === undefined || value === "normal") return 400;
  if (value === "bold") return 700;
  const n = Number(value);
  return Number.isFinite(n) ? n : 400;
}

function nearestFile(files: Partial<Record<Weight, string>>, wanted: number): string {
  const weights = (Object.keys(files).map(Number) as Weight[]).sort((x, y) => x - y);
  let best = weights[0];
  for (const w of weights) {
    // `<=` so that on a tie the heavier face wins (a request for 650 means "bolder", not "lighter").
    if (Math.abs(w - wanted) <= Math.abs(best - wanted)) best = w;
  }
  return files[best] as string;
}

export function fixTextStyle(style: TextStyle, opts: { android: boolean }): TextStyle {
  const out: TextStyle = { ...style };
  const family = out.fontFamily;
  const isCustom = typeof family === "string" && family.includes("_");

  if (out.fontWeight !== undefined && isCustom && family) {
    const files = FAMILY_FILES[family.split("_")[0]];
    const italic = family.includes("Italic");
    if (files && !italic) out.fontFamily = nearestFile(files, toWeight(out.fontWeight));
    delete out.fontWeight; // the weight now lives in the family file
  }

  if (isCustom && family && typeof out.fontSize === "number" && typeof out.lineHeight === "number") {
    const ratio = family.startsWith("Baloo2") ? DEVANAGARI_MIN_LINE_RATIO : DISPLAY_MIN_LINE_RATIO;
    const floor = Math.ceil(out.fontSize * ratio - 1e-9); // epsilon: 50 * 1.1 is 55.00000000000001
    if (out.lineHeight < floor) out.lineHeight = floor;
  }

  if (opts.android) out.includeFontPadding = false;
  return out;
}
