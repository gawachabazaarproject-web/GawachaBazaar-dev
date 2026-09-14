import React from "react";
import { StyleSheet, View } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Text } from "../Text";
import { EditorialLink } from "../EditorialLink";
import { colors, spacing } from "@/theme";

export interface VillageStoryProps {
  onPress?: () => void;
}

/** Real, already-authorized origin/ETA pairs (see productEmbellishments.ts)
 * re-presented as a stat row - mirrors the website's AerialLocation "35 KM
 * / KATOL ROAD BELT" pattern without inventing any new numbers. */
const ORIGIN_STATS = [
  { value: "22 MIN", label: "KATOL FARM" },
  { value: "25 MIN", label: "SAONER" },
  { value: "35 MIN", label: "WARDHA CLUSTER" },
];

/**
 * "From The Village" storytelling section - a single full-bleed image
 * panel (parallels the website's AerialLocation/VillageCulture sections),
 * grounded in the real origin villages already used throughout the app's
 * product-embellishment layer (Katol, Saoner, Wardha).
 */
export function VillageStory({ onPress }: VillageStoryProps) {
  return (
    <View style={styles.wrap}>
      <Image
        source="https://images.unsplash.com/photo-1500937386664-56d1dfef3854?w=1000&h=1200&fit=crop&q=80"
        style={StyleSheet.absoluteFill}
        contentFit="cover"
      />
      <LinearGradient
        pointerEvents="none"
        colors={["rgba(11,45,32,0)", "rgba(11,45,32,0.1)", "rgba(11,45,32,0.45)", "rgba(11,45,32,0.75)"]}
        locations={[0, 0.35, 0.7, 1]}
        style={StyleSheet.absoluteFill}
      />
      <View style={styles.content}>
        <Text variant="eyebrow" color={colors.accentLight}>
          FROM THE VILLAGE
        </Text>
        <Text variant="displayM" color={colors.textInverse} style={styles.headline}>
          Every crate begins{"\n"}in someone&apos;s{" "}
          <Text variant="script" color={colors.accentLight}>
            field.
          </Text>
        </Text>
        <Text variant="body" color="rgba(255,255,255,0.75)" style={styles.body}>
          Hand-graded in Katol, Saoner and Wardha by growers who&apos;ve worked this land for
          generations - then moved to your kitchen the same day, with no cold-storage detour.
        </Text>

        <View style={styles.statRow}>
          {ORIGIN_STATS.map((stat) => (
            <View key={stat.label} style={styles.stat}>
              <Text variant="h3" color={colors.textInverse}>
                {stat.value}
              </Text>
              <Text variant="label" color="rgba(255,255,255,0.55)" style={styles.statLabel}>
                {stat.label}
              </Text>
            </View>
          ))}
        </View>

        <EditorialLink tone="light" onPress={onPress} style={styles.link}>
          Meet our growers
        </EditorialLink>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { height: 560, marginTop: spacing.xl, overflow: "hidden", backgroundColor: colors.primary },
  content: { position: "absolute", left: spacing.base, right: spacing.base, bottom: spacing["2xl"] },
  headline: { marginTop: spacing.sm },
  body: { marginTop: spacing.base, maxWidth: "90%" },
  statRow: {
    flexDirection: "row",
    gap: spacing.xl,
    marginTop: spacing.xl,
    paddingTop: spacing.lg,
    borderTopWidth: 1,
    borderColor: "rgba(255,255,255,0.2)",
  },
  stat: { gap: 2 },
  statLabel: { marginTop: 2 },
  link: { marginTop: spacing.xl },
});
