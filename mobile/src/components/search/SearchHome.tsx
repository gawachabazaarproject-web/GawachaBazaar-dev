import React from "react";
import { Pressable, StyleSheet, useWindowDimensions, View } from "react-native";
import { Image, ImageSource } from "expo-image";
import { Feather } from "@expo/vector-icons";
import { Text } from "../Text";
import { colors, spacing } from "@/theme";

/** Horizontal screen padding of the Search landing design (18dp). */
export const SEARCH_PAD = 18;

const HERO_BAG = require("../../../assets/search/hero-bag.png");

const PILL_IMAGES: Record<string, ImageSource> = {
  tomato: require("../../../assets/search/pill-tomato.png"),
  onion: require("../../../assets/search/pill-onion.png"),
  milk: require("../../../assets/search/pill-milk.png"),
  rice: require("../../../assets/search/pill-rice.png"),
  bread: require("../../../assets/search/pill-bread.png"),
  dal: require("../../../assets/search/pill-dal.png"),
};

const CATEGORY_ART: { match: RegExp; art: ImageSource; subtitle: string }[] = [
  { match: /fruit/i, art: require("../../../assets/search/category-fruits.png"), subtitle: "Fresh & juicy fruits" },
  { match: /veg/i, art: require("../../../assets/search/category-vegetables.png"), subtitle: "Farm fresh vegetables" },
];

/** "SEARCH / What are you looking for?" hero with the Gawacha Bazaar bag
 * peeking in from the right. The bag sits behind the text column; the
 * search field below overlaps its bottom edge (rendered by the screen). */
export function SearchHero() {
  return (
    <View style={styles.hero}>
      <Image source={HERO_BAG} style={styles.heroBag} contentFit="contain" pointerEvents="none" />
      <Text variant="eyebrow" color={colors.accentDark}>
        SEARCH
      </Text>
      <Text variant="displayL" color={colors.primaryDark} style={styles.heroTitle}>
        What are you{"\n"}
        <Text variant="scriptLarge" color={colors.primaryDark} style={styles.heroScript}>
          looking for?
        </Text>
      </Text>
      <View style={styles.heroUnderline} />
      <Text variant="body" color={colors.textSecondary} style={styles.heroSubtitle}>
        Search for fresh fruits, vegetables and daily essentials
      </Text>
    </View>
  );
}

/** Small gold-ruled section label ("POPULAR SEARCHES ──"). */
export function SectionLabel({ children }: { children: string }) {
  return (
    <View style={styles.labelRow}>
      <Text variant="eyebrow" color={colors.accentDark} style={styles.labelText}>
        {children}
      </Text>
      <View style={styles.labelRule} />
    </View>
  );
}

export function PopularSearchPill({ term, onPress }: { term: string; onPress: () => void }) {
  const image = PILL_IMAGES[term.toLowerCase()];
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.pill, pressed && { opacity: 0.8 }]}
      accessibilityRole="button"
      accessibilityLabel={`Search ${term}`}
    >
      {image ? <Image source={image} style={styles.pillImage} contentFit="contain" /> : null}
      <Text variant="bodyMedium" color={colors.primaryDark} style={styles.pillText}>
        {term}
      </Text>
    </Pressable>
  );
}

export interface CategoryShowcase {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  image_url: string | null;
}

/** Two-up illustrated category cards ("Fruits ->  Fresh & juicy fruits").
 * Known categories use the designed artwork; any other category falls back
 * to its own admin-uploaded photo so new categories still look right. */
export function CategoryShowcaseGrid({
  categories,
  onPress,
}: {
  categories: CategoryShowcase[];
  onPress: (id: number) => void;
}) {
  const { width } = useWindowDimensions();
  const gap = 10;
  const cardWidth = (width - SEARCH_PAD * 2 - gap) / 2;

  return (
    <View style={[styles.cardGrid, { gap }]}>
      {categories.map((category) => {
        const known = CATEGORY_ART.find((c) => c.match.test(category.slug) || c.match.test(category.name));
        const subtitle = category.description?.trim() || known?.subtitle || `Shop ${category.name.toLowerCase()}`;
        return (
          <Pressable
            key={category.id}
            onPress={() => onPress(category.id)}
            style={({ pressed }) => [styles.card, { width: cardWidth }, pressed && { opacity: 0.9 }]}
            accessibilityRole="button"
            accessibilityLabel={`${category.name} category`}
          >
            <View style={styles.cardClip}>
              {known ? (
                <Image source={known.art} style={StyleSheet.absoluteFill} contentFit="cover" />
              ) : category.image_url ? (
                <Image source={category.image_url} style={styles.cardFallbackPhoto} contentFit="cover" />
              ) : null}
              <View style={styles.cardText}>
                <View style={styles.cardTitleRow}>
                  <Text variant="h2" color={colors.primaryDark} style={styles.cardTitle} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>
                    {category.name}
                  </Text>
                  <Feather name="arrow-right" size={17} color={colors.primaryDark} />
                </View>
                <Text variant="bodySmall" color={colors.textSecondary} style={styles.cardSubtitle} numberOfLines={2}>
                  {subtitle}
                </Text>
              </View>
            </View>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  // Heights below are measured from the design (dp): the hero ends exactly
  // where the search field begins, with the bag overlapping its top edge.
  // No fixed height: the title/script lines need their full line box or descenders clip.
  hero: { paddingHorizontal: SEARCH_PAD, paddingTop: 44, paddingBottom: 32, minHeight: 268 },
  // Bag artwork hangs from just under the header row, flush to the right edge.
  heroBag: { position: "absolute", right: 0, top: -21, width: 165, height: 221 },
  heroTitle: { marginTop: 12, fontSize: 36, lineHeight: 48 },
  heroScript: { fontSize: 40, lineHeight: 54 },
  heroUnderline: {
    width: 82,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.accent,
    marginTop: 4,
    marginLeft: 6,
  },
  heroSubtitle: { marginTop: 18, maxWidth: 200, fontSize: 15, lineHeight: 24 },

  labelRow: { flexDirection: "row", alignItems: "center", paddingHorizontal: SEARCH_PAD },
  labelText: { letterSpacing: 3, fontSize: 12 },
  labelRule: { width: 22, height: 1.5, backgroundColor: colors.accent, marginLeft: 12, borderRadius: 1 },

  pill: {
    flexDirection: "row",
    alignItems: "center",
    height: 42,
    borderRadius: 21,
    paddingLeft: 12,
    paddingRight: 24,
    gap: 14,
    minWidth: 104,
    backgroundColor: "#FBF9F2",
    borderWidth: 1,
    borderColor: colors.divider,
    shadowColor: "#143326",
    shadowOpacity: 0.06,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 1,
  },
  pillImage: { width: 30, height: 30 },
  pillText: { fontSize: 16, flexShrink: 1 },

  cardGrid: { flexDirection: "row", flexWrap: "wrap", paddingHorizontal: SEARCH_PAD },
  card: {
    height: 148,
    borderRadius: 20,
    backgroundColor: colors.surface,
    shadowColor: "#143326",
    shadowOpacity: 0.08,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  cardClip: {
    flex: 1,
    borderRadius: 20,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "#EFEADC",
    backgroundColor: "#F9F8F0",
  },
  cardFallbackPhoto: { position: "absolute", right: 0, bottom: 0, width: "46%", height: "72%", borderTopLeftRadius: 60 },
  cardText: { paddingTop: 22, paddingLeft: 16, paddingRight: 10 },
  cardTitleRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  cardTitle: { fontSize: 19, lineHeight: 27, flexShrink: 1 },
  cardSubtitle: { marginTop: 8, maxWidth: 84, fontSize: 12.5, lineHeight: 18 },
});
