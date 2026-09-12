import React from "react";
import { Text as RNText, TextProps as RNTextProps, TextStyle } from "react-native";
import { colors, typography } from "@/theme";

type Variant = keyof typeof typography;

export interface TextProps extends RNTextProps {
  variant?: Variant;
  color?: string;
  align?: TextStyle["textAlign"];
}

/** The one Text component every screen should use - guarantees every
 * label in the app comes from the type scale, never an ad hoc fontSize. */
export function Text({ variant = "body", color = colors.textPrimary, align, style, ...rest }: TextProps) {
  return <RNText style={[typography[variant], { color, textAlign: align }, style]} {...rest} />;
}
