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
};
