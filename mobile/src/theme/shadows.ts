import { Platform } from "react-native";
import { colors } from "./colors";

/** Two elevation levels only - a resting card and a raised sheet/modal.
 * Restrained on purpose: this app does not stack shadows on every card. */
function shadow(elevation: number, opacity: number, radius: number, height: number) {
  return Platform.select({
    ios: {
      shadowColor: colors.black,
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
  raised: shadow(8, 0.12, 20, 6),
};
