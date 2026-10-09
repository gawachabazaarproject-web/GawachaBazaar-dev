import React from "react";
import { StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { colors } from "@/theme";

// Source art is 1536x1024; only its top-right corner (x >= 1040, y < 400)
// is shown, scaled so that corner is ~130dp wide.
const SCALE = 0.262;
const SRC_W = 1536 * SCALE;
const SRC_H = 1024 * SCALE;
const CROP_LEFT = 1040 * SCALE;
const WIDTH = 130;
const HEIGHT = 84;
// Lines the art's own profile circle up with the real account button.
const OFFSET_TOP = -24;

const CLEAR = "rgba(247,244,235,0)";

/** Cropped farm-produce photo entering from the top-right of the cart
 * header; fades into the background on its left and bottom edges and sits
 * behind all header content. */
export function CartHeaderArt() {
  return (
    <View pointerEvents="none" style={styles.wrap}>
      <Image
        source={require("../../../assets/cart-header-produce.jpg")}
        style={{ position: "absolute", width: SRC_W, height: SRC_H, left: -CROP_LEFT, top: OFFSET_TOP }}
        contentFit="cover"
      />
      <LinearGradient
        colors={[colors.background, CLEAR]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={[StyleSheet.absoluteFill, { right: WIDTH * 0.6 }]}
      />
      <LinearGradient
        colors={[CLEAR, colors.background]}
        start={{ x: 0, y: 0 }}
        end={{ x: 0, y: 1 }}
        style={[StyleSheet.absoluteFill, { top: HEIGHT * 0.6 }]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: "absolute", top: 0, right: 0, width: WIDTH, height: HEIGHT, overflow: "hidden" },
});
