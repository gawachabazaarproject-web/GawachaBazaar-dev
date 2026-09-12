import React from "react";
import { View } from "react-native";
import { Text } from "./Text";
import { colors } from "@/theme";

/**
 * Text-based brand mark used until real logo assets exist (see
 * docs/API.md known limitations). Deliberately simple: two weights of
 * the same typeface, no icon invented on its behalf.
 */
export function Wordmark({ size = "lg" }: { size?: "lg" | "md" }) {
  return (
    <View style={{ flexDirection: "row" }}>
      <Text variant={size === "lg" ? "display" : "h1"} color={colors.primary}>
        Gawacha
      </Text>
      <Text variant={size === "lg" ? "display" : "h1"} color={colors.accent}>
        Bazaar
      </Text>
    </View>
  );
}
