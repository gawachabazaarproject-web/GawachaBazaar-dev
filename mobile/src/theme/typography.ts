import { TextStyle } from "react-native";

/**
 * Type system ported 1:1 from the Gawacha Bazaar website's font stack
 * (see website/app/layout.tsx + tailwind.config.ts): Bodoni Moda carries
 * every display/headline surface, Instrument Serif italic is the script
 * accent word inside headlines, Plus Jakarta Sans handles body/UI copy,
 * and Baloo 2 renders Devanagari (Marathi) text. Existing variant names
 * are preserved so no screen needs to change its `variant` prop - only
 * the underlying family/scale changed. New editorial-scale variants
 * (displayXL/L/M, script, eyebrow) were added for the redesign.
 */
export const fontFamily = {
  // display / headline family - Bodoni Moda
  headline: "BodoniModa_600SemiBold",
  headlineBold: "BodoniModa_700Bold",
  headlineExtraBold: "BodoniModa_800ExtraBold",
  headlineItalic: "BodoniModa_600SemiBold_Italic",
  // script / accent family - Instrument Serif italic (e.g. "the exact same" style words)
  script: "InstrumentSerif_400Regular_Italic",
  scriptRegular: "InstrumentSerif_400Regular",
  // body / UI family - Plus Jakarta Sans
  regular: "PlusJakartaSans_400Regular",
  medium: "PlusJakartaSans_500Medium",
  semibold: "PlusJakartaSans_600SemiBold",
  bold: "PlusJakartaSans_700Bold",
  extraBold: "PlusJakartaSans_800ExtraBold",
  // Devanagari (Marathi) family - Baloo 2
  devanagari: "Baloo2_600SemiBold",
  devanagariBold: "Baloo2_700Bold",
} as const;

type TypeStyle = Pick<TextStyle, "fontFamily" | "fontSize" | "lineHeight" | "letterSpacing" | "fontStyle">;

export const typography: Record<string, TypeStyle> = {
  // --- New editorial display scale (promotional carousel, hero statements) ---
  displayXL: { fontFamily: fontFamily.headlineBold, fontSize: 50, lineHeight: 52, letterSpacing: -0.8 },
  displayL: { fontFamily: fontFamily.headlineBold, fontSize: 34, lineHeight: 39, letterSpacing: -0.4 },
  displayM: { fontFamily: fontFamily.headline, fontSize: 26, lineHeight: 31, letterSpacing: -0.3 },
  // Instrument Serif italic accent - one or two words inside a headline
  scriptLarge: { fontFamily: fontFamily.script, fontSize: 42, lineHeight: 46, fontStyle: "italic" },
  script: { fontFamily: fontFamily.script, fontSize: 28, lineHeight: 33, fontStyle: "italic" },
  scriptSmall: { fontFamily: fontFamily.script, fontSize: 19, lineHeight: 23, fontStyle: "italic" },
  // eyebrow / chapter-numbering micro-label ("01/08 — Today's Market")
  eyebrow: { fontFamily: fontFamily.bold, fontSize: 11, lineHeight: 14, letterSpacing: 2.2 },

  // --- Existing scale, family swapped to Bodoni Moda / kept size-compatible ---
  // headline-lg (desktop) - reserved for the wordmark only
  display: { fontFamily: fontFamily.headlineBold, fontSize: 30, lineHeight: 38, letterSpacing: -0.3 },
  // headline-lg-mobile - screen titles ("Categories", "Your orders")
  h1: { fontFamily: fontFamily.headlineBold, fontSize: 26, lineHeight: 33, letterSpacing: -0.24 },
  // headline-md - section headers ("Shop by category")
  h2: { fontFamily: fontFamily.headline, fontSize: 22, lineHeight: 29 },
  // headline-sm - card/sheet titles
  h3: { fontFamily: fontFamily.headline, fontSize: 18, lineHeight: 25 },
  bodyLarge: { fontFamily: fontFamily.regular, fontSize: 16, lineHeight: 23 },
  // body-md
  body: { fontFamily: fontFamily.regular, fontSize: 14, lineHeight: 21 },
  // title-md
  bodyMedium: { fontFamily: fontFamily.semibold, fontSize: 15, lineHeight: 21 },
  // title-sm - compact semibold text (product card titles, chip labels)
  titleSmall: { fontFamily: fontFamily.semibold, fontSize: 13, lineHeight: 19 },
  bodySmall: { fontFamily: fontFamily.regular, fontSize: 13, lineHeight: 19 },
  // body-sm
  caption: { fontFamily: fontFamily.regular, fontSize: 12, lineHeight: 17 },
  // label-md
  captionMedium: { fontFamily: fontFamily.semibold, fontSize: 11, lineHeight: 15, letterSpacing: 0.22 },
  // label-xs
  label: { fontFamily: fontFamily.bold, fontSize: 10, lineHeight: 13, letterSpacing: 0.4 },
  // price-lg
  price: { fontFamily: fontFamily.bold, fontSize: 16, lineHeight: 20, letterSpacing: -0.32 },
  priceLarge: { fontFamily: fontFamily.bold, fontSize: 24, lineHeight: 30, letterSpacing: -0.4 },
  // title-sm
  priceSmall: { fontFamily: fontFamily.bold, fontSize: 13, lineHeight: 16 },
  // title-md
  button: { fontFamily: fontFamily.semibold, fontSize: 15, lineHeight: 20 },
};
