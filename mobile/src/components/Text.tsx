import React from "react";
import { Platform, StyleSheet, Text as RNText, TextProps as RNTextProps, TextStyle } from "react-native";
import { colors, typography } from "@/theme";
import { fixTextStyle } from "@/theme/textStyle";

type Variant = keyof typeof typography;

export interface TextProps extends RNTextProps {
  variant?: Variant;
  color?: string;
  align?: TextStyle["textAlign"];
}

const IS_ANDROID = Platform.OS === "android";

/** The one Text component every screen should use - guarantees every
 * label in the app comes from the type scale, never an ad hoc fontSize.
 *
 * The merged style goes through fixTextStyle (theme/textStyle.ts), which stops
 * stacked-bold / clipped / misaligned text on small and older Android phones
 * without changing the design. */
export function Text({ variant = "body", color = colors.textPrimary, align, style, ...rest }: TextProps) {
  const merged = StyleSheet.flatten([typography[variant], { color, textAlign: align }, style]) as TextStyle;
  return (
    <RNText
      maxFontSizeMultiplier={1.15}
      style={fixTextStyle(merged, { android: IS_ANDROID })}
      {...rest}
    />
  );
}
