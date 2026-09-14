import { WithSpringConfig, WithTimingConfig } from "react-native-reanimated";

/**
 * Motion tokens - every animation in the app should reference one of
 * these instead of inventing spring/timing constants ad hoc. Springs are
 * tuned to feel quick and controlled, never bouncy.
 */
export const springs: Record<string, WithSpringConfig> = {
  snappy: { damping: 20, stiffness: 260, mass: 0.6 },
  gentle: { damping: 18, stiffness: 160, mass: 0.8 },
};

export const timings: Record<string, WithTimingConfig> = {
  fast: { duration: 150 },
  base: { duration: 220 },
  slow: { duration: 320 },
  // Cinematic-length transitions for the promotional carousel (campaign
  // slide changes) - matches the website's ~700-1200ms editorial easing.
  cinematic: { duration: 850 },
  cinematicSlow: { duration: 1100 },
};

/** Matches the website's `transitionTimingFunction.editorial` cubic-bezier. */
export const editorialEasing = { x1: 0.65, y1: 0, x2: 0.35, y2: 1 } as const;
