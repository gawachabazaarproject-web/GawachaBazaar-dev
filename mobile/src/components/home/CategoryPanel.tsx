import React from "react";
import { StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Feather } from "@expo/vector-icons";
import { PressableScale } from "../PressableScale";
import { Text } from "../Text";
import { getCategoryPhoto } from "@/utils/categoryVisuals";
import { CATEGORY_MARATHI } from "@/utils/categoryDepartments";
import { colors, radius, spacing } from "@/theme";

export interface CategoryPanelProps {
  id: number;
  slug: string;
  name: string;
  index: number;
  onPress: () => void;
}

const PANEL_WIDTH = 168;
const PANEL_HEIGHT = 226;

/** Large visual "shop by category" panel - dominant photography and
 * editorial typography, replacing the old small circular icon+label
 * tile. Horizontally scrollable on Home. */
export function CategoryPanel({ slug, name, index, onPress }: CategoryPanelProps) {
  const marathiName = CATEGORY_MARATHI[slug];

  return (
    <PressableScale onPress={onPress} style={styles.panel}>
      <Image source={getCategoryPhoto(slug)} style={StyleSheet.absoluteFill} contentFit="cover" transition={200} />
      <LinearGradient
        pointerEvents="none"
        colors={["rgba(11,45,32,0.22)", "rgba(11,45,32,0)", "rgba(11,45,32,0.35)", "rgba(11,45,32,0.62)"]}
        locations={[0, 0.35, 0.7, 1]}
        style={StyleSheet.absoluteFill}
      />
      <Text variant="eyebrow" color="rgba(255,255,255,0.55)" style={styles.index}>
        {String(index + 1).padStart(2, "0")}
      </Text>
      <View style={styles.footer}>
        <View style={{ flex: 1 }}>
          <Text variant="titleSmall" color={colors.textInverse} numberOfLines={1}>
            {name}
          </Text>
          {marathiName ? (
            <Text variant="caption" color="rgba(255,255,255,0.7)" numberOfLines={1}>
              {marathiName}
            </Text>
          ) : null}
        </View>
        <View style={styles.arrow}>
          <Feather name="arrow-up-right" size={14} color={colors.textInverse} />
        </View>
      </View>
    </PressableScale>
  );
}

const styles = StyleSheet.create({
  panel: {
    width: PANEL_WIDTH,
    height: PANEL_HEIGHT,
    borderRadius: radius.xs,
    // Clips the absolutely-positioned image/gradient to the rounded shape
    // above - without this, they'd stay square and visibly poke out past
    // the panel's rounded corners.
    overflow: "hidden",
    backgroundColor: colors.primary,
    justifyContent: "space-between",
  },
  index: { padding: spacing.md },
  footer: {
    flexDirection: "row",
    alignItems: "flex-end",
    padding: spacing.md,
    gap: spacing.sm,
  },
  arrow: {
    width: 26,
    height: 26,
    borderRadius: radius.none,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.5)",
    alignItems: "center",
    justifyContent: "center",
  },
});
