import { Platform } from "react-native";
import { colors } from "./colors";

/**
 * Two elevation levels, both forest-tinted (see DESIGN.md's elevation
 * system: shadows keyed off the brand primary rather than pure black, so
 * depth reads as organic/biological rather than industrial grey).
 * Restrained on purpose - this app does not stack shadows on every card.
 */
function shadow(elevation: number, opacity: number, radius: number, height: number) {
  return Platform.select({
    ios: {
      shadowColor: colors.primary,
      shadowOpacity: opacity,
      shadowRadius: radius,
      shadowOffset: { width: 0, height },
    },
    android: { elevation },
    default: {},
  });
}

export const shadows = {
  card: shadow(2, 0.06, 8, 2),
  raised: shadow(8, 0.14, 16, 4),
};
