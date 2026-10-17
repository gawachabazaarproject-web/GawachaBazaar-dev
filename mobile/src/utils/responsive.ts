/**
 * Small-screen scaling for fixed-size decorative art and hero headings.
 *
 * The design is drawn for ~360dp-wide phones. On narrower screens (older /
 * compact phones, 320-359dp) fixed-pixel art and large headings crowd or
 * overlap the text beside them. `smallScreenScale` returns 1 for any screen
 * 360dp or wider, so those layouts are left exactly as designed, and shrinks
 * proportionally below that (never under 0.85, so nothing becomes tiny).
 */
export const DESIGN_WIDTH = 360;
const MIN_SCALE = 0.85;

export function smallScreenScale(windowWidth: number): number {
  if (!Number.isFinite(windowWidth) || windowWidth <= 0) return 1;
  return Math.max(MIN_SCALE, Math.min(1, windowWidth / DESIGN_WIDTH));
}

/** Scales a design pixel value; identity when scale is 1. */
export function scaled(value: number, scale: number): number {
  return scale >= 1 ? value : Math.round(value * scale);
}
