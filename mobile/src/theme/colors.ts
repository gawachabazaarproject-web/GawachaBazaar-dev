/**
 * GawachaBazaar color tokens.
 *
 * Design intent: deep forest green (trust, freshness) as the restrained
 * primary - never a bright "grocery green" wash. A warm terracotta accent
 * carries CTAs and price emphasis, giving the palette an Indian warmth
 * without falling back on leaf/vegetable clichés. Background is a warm
 * off-white, not stark white or gray, so photography and product imagery
 * feel inviting rather than clinical.
 *
 * Only this file may define raw color values - every screen/component
 * reads from `colors`, never a hex literal inline.
 */

export const colors = {
  // Brand
  primary: "#1F6D4C",
  primaryDark: "#154A34",
  primaryLight: "#E7F1EC",
  accent: "#E8622C",
  accentDark: "#C64F1F",
  accentLight: "#FBEAE1",

  // Surfaces
  background: "#FAF9F6",
  surface: "#FFFFFF",
  surfaceElevated: "#FFFFFF",
  overlay: "rgba(20, 20, 18, 0.5)",

  // Text
  textPrimary: "#1A1A18",
  textSecondary: "#6B6B63",
  textMuted: "#9B9B92",
  textInverse: "#FFFFFF",
  textOnAccent: "#FFFFFF",

  // Structure
  border: "#E8E6DF",
  borderStrong: "#D3D0C6",
  divider: "#EFEDE6",

  // Status
  success: "#1E8E5A",
  successLight: "#E5F4EC",
  warning: "#C9821A",
  warningLight: "#FBF0DE",
  error: "#D6412F",
  errorLight: "#FBEAE7",
  info: "#2E6FBB",
  infoLight: "#E9F1FA",

  // Commerce-specific
  price: "#1A1A18",
  discount: "#1E8E5A",
  strikethrough: "#9B9B92",

  // Fixed
  white: "#FFFFFF",
  black: "#000000",
  transparent: "transparent",
} as const;

export type ColorToken = keyof typeof colors;
