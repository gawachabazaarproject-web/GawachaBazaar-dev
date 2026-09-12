import React from "react";
import { StyleSheet, View, ViewStyle } from "react-native";
import { SafeAreaView, Edge } from "react-native-safe-area-context";
import { colors } from "@/theme";

export interface ScreenProps {
  children: React.ReactNode;
  edges?: Edge[];
  backgroundColor?: string;
  style?: ViewStyle;
}

/** Standard screen shell - safe-area aware, consistent background. Use
 * `edges` to opt individual screens out of top/bottom padding (e.g. a
 * screen with its own custom header). */
export function Screen({ children, edges = ["top", "bottom"], backgroundColor = colors.background, style }: ScreenProps) {
  return (
    <SafeAreaView edges={edges} style={[styles.container, { backgroundColor }, style]}>
      {children}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
});
