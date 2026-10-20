import React from "react";
import { StyleSheet, useWindowDimensions, View } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Feather } from "@expo/vector-icons";
import { useQueries } from "@tanstack/react-query";
import { catalogApi } from "@/api";
import { PressableScale } from "../PressableScale";
import { Text } from "../Text";
import { getCategoryPhoto } from "@/utils/categoryVisuals";
import { CategoryResponse } from "@/types/api";
import { colors, radius, spacing } from "@/theme";

const GAP = spacing.sm;
const MAX_TILES = 6;

export interface SubcategoryBentoProps {
  /** Top-level categories already in the admin-chosen order. */
  categories: CategoryResponse[];
  onPress: (category: CategoryResponse) => void;
}

interface Tile {
  sub: CategoryResponse;
  parentName: string;
}

/**
 * Bento grid of subcategories. Order follows the admin panel's "Display
 * order": categories in their order, each one's subcategories in theirs,
 * so whatever the admin puts first gets the big hero tile.
 *
 * Layout (6 tiles): one tall hero beside two stacked tiles, then a row of
 * three. Fewer tiles degrade to simpler rows rather than leaving gaps.
 */
export function SubcategoryBento({ categories, onPress }: SubcategoryBentoProps) {
  const { width } = useWindowDimensions();
  const results = useQueries({
    queries: categories.map((c) => ({
      queryKey: ["categories", "children", c.id],
      queryFn: () => catalogApi.listCategories(c.id),
      staleTime: 5 * 60_000,
      enabled: (c.child_count ?? 0) > 0,
    })),
  });

  const tiles: Tile[] = [];
  categories.forEach((parent, i) => {
    for (const sub of results[i]?.data ?? []) tiles.push({ sub, parentName: parent.name });
  });
  const shown = tiles.slice(0, MAX_TILES);
  if (shown.length === 0) return null;

  const inner = width - spacing.base * 2;
  const unit = (inner - GAP) / 2; // hero + stack split: hero is 1.2x
  const heroW = Math.round(unit * 1.2);
  const stackW = inner - GAP - heroW;
  const heroH = Math.round(heroW * 1.12);
  const smallH = (heroH - GAP) / 2;

  const render = (tile: Tile, w: number, h: number, feature = false) => (
    <BentoTile key={tile.sub.id} tile={tile} width={w} height={h} feature={feature} onPress={() => onPress(tile.sub)} />
  );

  const [hero, a, b, ...rest] = shown;
  const lone = shown.length < 3;

  return (
    <View style={styles.wrap}>
      {lone ? (
        <View style={styles.row}>
          {shown.map((t) => render(t, (inner - GAP * (shown.length - 1)) / shown.length, 170, shown.length === 1))}
        </View>
      ) : (
        <>
          <View style={styles.row}>
            {render(hero, heroW, heroH, true)}
            <View style={{ gap: GAP }}>
              {render(a, stackW, smallH)}
              {render(b, stackW, smallH)}
            </View>
          </View>
          {rest.length > 0 ? (
            <View style={[styles.row, { marginTop: GAP }]}>
              {rest.map((t) => render(t, (inner - GAP * (rest.length - 1)) / rest.length, 124))}
            </View>
          ) : null}
        </>
      )}
    </View>
  );
}

function BentoTile({
  tile,
  width,
  height,
  feature,
  onPress,
}: {
  tile: Tile;
  width: number;
  height: number;
  feature: boolean;
  onPress: () => void;
}) {
  const { sub, parentName } = tile;
  const count = sub.product_count ?? 0;
  return (
    <PressableScale onPress={onPress} style={[styles.tile, { width, height }]}>
      <Image source={getCategoryPhoto(sub.slug, sub.image_url)} style={StyleSheet.absoluteFill} contentFit="cover" transition={200} />
      <LinearGradient
        pointerEvents="none"
        colors={["rgba(11,45,32,0.1)", "rgba(11,45,32,0.15)", "rgba(11,45,32,0.78)"]}
        locations={[0, 0.4, 1]}
        style={StyleSheet.absoluteFill}
      />
      <View style={styles.topRow}>
        <Text variant="eyebrow" color="rgba(255,255,255,0.75)" numberOfLines={1} style={{ flexShrink: 1 }}>
          {parentName.toUpperCase()}
        </Text>
        <View style={styles.arrow}>
          <Feather name="arrow-up-right" size={12} color={colors.textInverse} />
        </View>
      </View>
      <View style={styles.footer}>
        <Text variant={feature ? "h3" : "bodyMedium"} color={colors.textInverse} numberOfLines={2}>
          {sub.name}
        </Text>
        {count > 0 ? (
          <Text variant="caption" color="rgba(255,255,255,0.75)" numberOfLines={1}>
            {count} {count === 1 ? "item" : "items"}
          </Text>
        ) : null}
      </View>
    </PressableScale>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: spacing.base },
  row: { flexDirection: "row", gap: GAP },
  tile: {
    borderRadius: radius.card,
    overflow: "hidden",
    backgroundColor: colors.primary,
    justifyContent: "space-between",
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.xs,
    padding: spacing.sm,
  },
  arrow: {
    width: 22,
    height: 22,
    borderRadius: radius.card,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.5)",
    alignItems: "center",
    justifyContent: "center",
  },
  footer: { padding: spacing.sm, gap: 2 },
});
