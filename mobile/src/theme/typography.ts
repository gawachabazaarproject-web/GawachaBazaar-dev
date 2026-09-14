import { TextStyle } from "react-native";

/**
 * Dual-engine type system (see DESIGN.md): Noto Serif carries brand/
 * heritage headlines, Plus Jakarta Sans handles every operational
 * surface - prices, labels, body copy - optimized for fast scanning.
 * Sizes/weights below are DESIGN.md's documented scale, mapped onto this
 * app's existing variant names (mobile headline sizes, not desktop).
 */
export const fontFamily = {
  headline: "NotoSerif_600SemiBold",
  headlineBold: "NotoSerif_700Bold",
  regular: "PlusJakartaSans_400Regular",
  medium: "PlusJakartaSans_500Medium",
  semibold: "PlusJakartaSans_600SemiBold",
  bold: "PlusJakartaSans_700Bold",
} as const;

type TypeStyle = Pick<TextStyle, "fontFamily" | "fontSize" | "lineHeight" | "letterSpacing">;

export const typography: Record<string, TypeStyle> = {
  // headline-lg (desktop) - reserved for the wordmark only
  display: { fontFamily: fontFamily.headlineBold, fontSize: 30, lineHeight: 38, letterSpacing: -0.3 },
  // headline-lg-mobile - screen titles ("Categories", "Your orders")
  h1: { fontFamily: fontFamily.headlineBold, fontSize: 24, lineHeight: 32, letterSpacing: -0.24 },
  // headline-md - section headers ("Shop by category")
  h2: { fontFamily: fontFamily.headline, fontSize: 20, lineHeight: 28 },
  // headline-sm - card/sheet titles
  h3: { fontFamily: fontFamily.headline, fontSize: 17, lineHeight: 24 },
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
