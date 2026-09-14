/** Restrained spacing scale - every margin/padding/gap in the app should
 * come from here, never a raw number, so rhythm stays consistent. */
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  base: 16,
  lg: 20,
  xl: 24,
  "2xl": 32,
  "3xl": 40,
  "4xl": 48,
} as const;

export type SpacingToken = keyof typeof spacing;

export const radius = {
  // De-roundified, editorial default - matches the website's `rounded-none`
  // philosophy. Prefer this on new cards/images/panels; the larger values
  // below remain only for genuinely circular controls (avatars, dots).
  none: 0,
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  pill: 999,
} as const;

export type RadiusToken = keyof typeof radius;
