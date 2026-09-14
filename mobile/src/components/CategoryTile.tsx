import React from "react";
import { StyleSheet } from "react-native";
import { Image } from "expo-image";
import { getCategoryPhoto } from "@/utils/categoryVisuals";
import { colors } from "@/theme";

export interface CategoryTileProps {
  slug: string;
  size?: number;
}

/** Circular category photo thumbnail shared by Home's category rail and
 * the Categories tab list - the one place category imagery is defined. */
export function CategoryTile({ slug, size = 56 }: CategoryTileProps) {
  return (
    <Image
      source={getCategoryPhoto(slug)}
      style={[styles.tile, { width: size, height: size, borderRadius: size / 2 }]}
      contentFit="cover"
      transition={150}
    />
  );
}

const styles = StyleSheet.create({
  tile: { backgroundColor: colors.divider },
});
