import { TextStyle } from "react-native";

/**
 * One typeface family (Inter), restrained weight set. No secondary
 * display face - hierarchy comes from size/weight/color, not font mixing.
 */
export const fontFamily = {
  regular: "Inter_400Regular",
  medium: "Inter_500Medium",
  semibold: "Inter_600SemiBold",
  bold: "Inter_700Bold",
} as const;

type TypeStyle = Pick<TextStyle, "fontFamily" | "fontSize" | "lineHeight" | "letterSpacing">;

export const typography: Record<string, TypeStyle> = {
  display: { fontFamily: fontFamily.bold, fontSize: 28, lineHeight: 34, letterSpacing: -0.3 },
  h1: { fontFamily: fontFamily.bold, fontSize: 22, lineHeight: 28, letterSpacing: -0.2 },
  h2: { fontFamily: fontFamily.semibold, fontSize: 18, lineHeight: 24 },
  h3: { fontFamily: fontFamily.semibold, fontSize: 16, lineHeight: 22 },
  bodyLarge: { fontFamily: fontFamily.regular, fontSize: 16, lineHeight: 22 },
  body: { fontFamily: fontFamily.regular, fontSize: 14, lineHeight: 20 },
  bodyMedium: { fontFamily: fontFamily.medium, fontSize: 14, lineHeight: 20 },
  bodySmall: { fontFamily: fontFamily.regular, fontSize: 13, lineHeight: 18 },
  caption: { fontFamily: fontFamily.regular, fontSize: 12, lineHeight: 16 },
  captionMedium: { fontFamily: fontFamily.medium, fontSize: 12, lineHeight: 16 },
  label: { fontFamily: fontFamily.semibold, fontSize: 11, lineHeight: 14, letterSpacing: 0.4 },
  price: { fontFamily: fontFamily.bold, fontSize: 16, lineHeight: 20 },
  priceLarge: { fontFamily: fontFamily.bold, fontSize: 22, lineHeight: 28 },
  button: { fontFamily: fontFamily.semibold, fontSize: 15, lineHeight: 20 },
};
