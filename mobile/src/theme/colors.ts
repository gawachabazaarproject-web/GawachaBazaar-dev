/**
 * GawachaBazaar color tokens - "Refined Organic Commerce" design system
 * (see DESIGN.md): deep forest green anchoring the brand, golden mustard
 * as a high-conversion accent, warm harvest-cream canvas. Honors Nagpur's
 * agricultural belts - deep forest cover, sun-dried pulse fields, and
 * unbleached grain sacks - without generic "grocery green" cliché.
 *
 * Only this file may define raw color values - every screen/component
 * reads from `colors`, never a hex literal inline.
 */

export const colors = {
  // Brand
  primary: "#0B2D20",
  primaryDark: "#0F3B2B",
  primaryLight: "#C6EBD7",
  accent: "#D9A52A",
  accentDark: "#7A5900",
  accentLight: "#FFDEA2",

  // Surfaces
  background: "#F7F4EB",
  surface: "#FFFFFF",
  surfaceElevated: "#FFFFFF",
  overlay: "rgba(11, 45, 32, 0.4)",

  // Text
  textPrimary: "#143326",
  textSecondary: "#506155",
  textMuted: "#8C9B90",
  textInverse: "#FFFFFF",
  textOnAccent: "#0B2D20",

  // Structure
  border: "#E2DDD0",
  borderStrong: "#D5CEC2",
  divider: "#EBE5D5",

  // Status
  success: "#1E8E5A",
  successLight: "#E5F4EC",
  warning: "#C9821A",
  warningLight: "#FBF0DE",
  error: "#BA1A1A",
  errorLight: "#FFDAD6",
  info: "#2E6FBB",
  infoLight: "#E9F1FA",

  // Commerce-specific
  price: "#143326",
  discount: "#1E8E5A",
  strikethrough: "#8C9B90",

  // Fixed
  white: "#FFFFFF",
  black: "#000000",
  transparent: "transparent",
} as const;

export type ColorToken = keyof typeof colors;
