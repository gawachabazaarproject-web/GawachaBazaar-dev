import React from "react";
import { StyleSheet, View, useWindowDimensions } from "react-native";
import { Image } from "expo-image";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import Animated, { FadeInDown } from "react-native-reanimated";
import { PressableScale } from "../PressableScale";
import { Text } from "../Text";
import { CategoryResponse } from "@/types/api";
import { colors, radius, spacing } from "@/theme";

type IconName = React.ComponentProps<typeof MaterialCommunityIcons>["name"];

/** Shown only for a category the admin has not given an illustration yet. */
const FALLBACK_ICONS: [RegExp, IconName][] = [
  [/fruit/i, "food-apple"],
  [/veg/i, "carrot"],
  [/dairy|milk|paneer/i, "cow"],
  [/bakery|bread/i, "baguette"],
  [/cloth|apparel|fashion|wear/i, "tshirt-crew"],
  [/grocer|staple|grain|rice|pulse|flour/i, "basket"],
  [/bever|drink|juice/i, "bottle-soda"],
  [/snack|biscuit/i, "cookie"],
  [/house|clean|home/i, "home-variant"],
  [/care|beauty|skin/i, "spa"],
];

export function fallbackIconFor(category: Pick<CategoryResponse, "name" | "slug">): IconName {
  const hay = `${category.name} ${category.slug}`;
  return FALLBACK_ICONS.find(([re]) => re.test(hay))?.[1] ?? "shopping";
}

export interface CategoryGridProps {
  categories: CategoryResponse[];
  onPress: (category: CategoryResponse) => void;
  /** Cap the number of tiles (Home shows a short grid; View all shows everything). */
  limit?: number;
}

/**
 * Admin-controlled "shop by category" grid: an illustration on a tinted
 * rounded tile with the name underneath. Everything shown - which
 * categories, their order, image, tint and badge - comes from the API.
 */
export function CategoryGrid({ categories, onPress, limit }: CategoryGridProps) {
  const { width } = useWindowDimensions();
  const columns = width < 340 ? 3 : 4;
  const gap = spacing.sm;
  const tile = Math.floor((width - spacing.base * 2 - gap * (columns - 1)) / columns);
  const shown = limit ? categories.slice(0, limit) : categories;

  return (
    <View style={[styles.grid, { paddingHorizontal: spacing.base, gap }]}>
      {shown.map((category, index) => (
        <Animated.View
          key={category.id}
          entering={FadeInDown.delay(Math.min(index, 8) * 40).duration(240)}
          style={{ width: tile }}
        >
          <PressableScale
            onPress={() => onPress(category)}
            accessibilityRole="button"
            accessibilityLabel={category.name}
            style={styles.cell}
          >
            <View
              style={[
                styles.iconBox,
                { width: tile, height: tile, backgroundColor: category.background_color ?? colors.surfaceTint },
              ]}
            >
              {category.image_url ? (
                <Image source={category.image_url} style={styles.image} contentFit="contain" transition={150} />
              ) : (
                <MaterialCommunityIcons name={fallbackIconFor(category)} size={tile * 0.46} color={colors.primary} />
              )}
              {category.badge_text ? (
                <View style={styles.badge}>
                  <Text variant="caption" color={colors.textOnAccent} numberOfLines={1} style={styles.badgeText}>
                    {category.badge_text}
                  </Text>
                </View>
              ) : null}
            </View>
            <Text variant="caption" color={colors.textPrimary} numberOfLines={2} style={styles.label}>
              {category.name}
            </Text>
          </PressableScale>
        </Animated.View>
      ))}
    </View>
  );
}

export function CategoryGridSkeleton() {
  const { width } = useWindowDimensions();
  const columns = width < 340 ? 3 : 4;
  const gap = spacing.sm;
  const tile = Math.floor((width - spacing.base * 2 - gap * (columns - 1)) / columns);
  return (
    <View style={[styles.grid, { paddingHorizontal: spacing.base, gap }]}>
      {Array.from({ length: columns * 2 }).map((_, i) => (
        <View key={i} style={{ width: tile }}>
          <View style={[styles.iconBox, { width: tile, height: tile, backgroundColor: colors.surfaceTint, opacity: 0.6 }]} />
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: "row", flexWrap: "wrap", rowGap: spacing.base },
  cell: { alignItems: "center" },
  iconBox: {
    borderRadius: radius.card,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  image: { width: "80%", height: "80%" },
  label: { marginTop: spacing.xs, textAlign: "center", minHeight: 34 },
  badge: {
    position: "absolute",
    top: spacing.xs,
    left: spacing.xs,
    maxWidth: "90%",
    paddingHorizontal: spacing.xs,
    paddingVertical: 1,
    borderRadius: radius.card,
    backgroundColor: colors.accent,
  },
  badgeText: { fontSize: 10, lineHeight: 14, fontWeight: "700" },
});
