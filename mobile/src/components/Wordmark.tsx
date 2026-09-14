import React from "react";
import { Image } from "expo-image";
import { StyleSheet, View } from "react-native";

const LOGO_ASPECT_RATIO = 1369 / 1149;
const LOGO_BACKGROUND = "#000F08";

/**
 * The real GawachaBazaar logo (assets/logo.jpeg) - replaces the earlier
 * text-based stand-in now that a real brand asset exists. The source
 * JPEG has no transparency (its own dark background is baked in), so
 * it's presented as a rounded badge/seal rather than floating bare on
 * the app's light background, which would otherwise show a stray
 * rectangle around it. Centered, with a soft radius - the one spot in the
 * app where a rounded "seal" reads as a mark rather than a container.
 */
export function Wordmark({ size = "lg" }: { size?: "lg" | "md" }) {
  const height = size === "lg" ? 84 : 56;
  const padding = size === "lg" ? 16 : 10;
  return (
    <View style={[styles.badge, { padding, borderRadius: 20 }]}>
      <Image
        source={require("../../assets/logo.jpeg")}
        style={{ height, width: height * LOGO_ASPECT_RATIO, borderRadius: 12 }}
        contentFit="contain"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: "center",
    backgroundColor: LOGO_BACKGROUND,
  },
});
