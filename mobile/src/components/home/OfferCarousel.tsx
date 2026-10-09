import React, { useCallback, useState } from "react";
import { Pressable, ScrollView, StyleSheet, useWindowDimensions, View } from "react-native";
import { useRouter } from "expo-router";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { Text } from "../Text";
import { useOffers } from "@/features/offers/useOffers";
import { usePendingPromoStore } from "@/store/pendingPromoStore";
import { colors, radius, spacing } from "@/theme";
import { OfferResponse } from "@/types/api";

const CARD_HEIGHT = 214;
const CARD_GAP = spacing.md;
const SIDE = spacing.base;

/**
 * "Offers for you" - live promotions the admin switched on for the Home
 * carousel (Admin -> Promotions -> "Show in app carousel"). Each card shows
 * the banner photo, the headline, the code to use and its fine print.
 * Tapping a card remembers its code so checkout applies it automatically;
 * the discount itself is always computed by the backend at checkout.
 * Renders nothing when there are no live offers.
 */
export function OfferCarousel() {
  const router = useRouter();
  const { data: offers } = useOffers();
  const { width } = useWindowDimensions();
  const setPendingCode = usePendingPromoStore((s) => s.set);
  const [active, setActive] = useState(0);
  const [savedId, setSavedId] = useState<number | null>(null);

  const cardWidth = Math.min(width * 0.8, 340);
  const stride = cardWidth + CARD_GAP;

  const handlePress = useCallback(
    (offer: OfferResponse) => {
      Haptics.selectionAsync().catch(() => undefined);
      if (offer.code) {
        setPendingCode(offer.code);
        setSavedId(offer.id);
        setTimeout(() => setSavedId((id) => (id === offer.id ? null : id)), 2500);
      }
      router.push("/(tabs)/categories");
    },
    [router, setPendingCode],
  );

  if (!offers || offers.length === 0) return null;

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <Text variant="eyebrow" color={colors.accentLight}>
          OFFERS FOR YOU
        </Text>
        <Text variant="displayM" color={colors.textInverse} style={styles.title}>
          Save more on every{" "}
          <Text variant="script" color={colors.accentLight}>
            Bazaar.
          </Text>
        </Text>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        snapToInterval={stride}
        decelerationRate="fast"
        contentContainerStyle={styles.row}
        onMomentumScrollEnd={(e) => setActive(Math.round(e.nativeEvent.contentOffset.x / stride))}
      >
        {offers.map((offer, index) => (
          <Pressable
            key={offer.id}
            onPress={() => handlePress(offer)}
            style={[styles.card, { width: cardWidth, marginRight: index < offers.length - 1 ? CARD_GAP : 0 }]}
            accessibilityRole="button"
            accessibilityLabel={`${offer.title}. ${offer.code ? `Use code ${offer.code}` : "Applied automatically"}`}
          >
            {offer.image_url ? (
              <Image source={offer.image_url} style={StyleSheet.absoluteFill} contentFit="cover" transition={200} />
            ) : null}
            <LinearGradient
              pointerEvents="none"
              colors={["rgba(6,26,18,0.05)", "rgba(6,26,18,0.55)", "rgba(6,26,18,0.92)"]}
              locations={[0.1, 0.55, 1]}
              style={StyleSheet.absoluteFill}
            />

            <View style={styles.badgeRow}>
              <View style={styles.discountBadge}>
                <Text variant="eyebrow" color={colors.primaryDark} style={styles.badgeText}>
                  {offer.discount_label}
                </Text>
              </View>
              {offer.audience ? (
                <View style={styles.audienceChip}>
                  <Text variant="caption" color={colors.textInverse}>
                    {offer.audience}
                  </Text>
                </View>
              ) : null}
            </View>

            <View style={styles.content}>
              <Text variant="h2" color={colors.textInverse} numberOfLines={2} style={styles.offerTitle}>
                {offer.title}
              </Text>
              {offer.description ? (
                <Text variant="bodySmall" color="rgba(255,255,255,0.82)" numberOfLines={2} style={styles.offerBody}>
                  {offer.description}
                </Text>
              ) : null}
              <View style={styles.footerRow}>
                <View style={styles.codeChip}>
                  <Feather name={offer.code ? "tag" : "zap"} size={13} color={colors.accentLight} />
                  <Text variant="eyebrow" color={colors.accentLight} style={styles.codeText}>
                    {savedId === offer.id ? "CODE SAVED FOR CHECKOUT" : offer.code ? `CODE ${offer.code}` : "AUTO-APPLIED"}
                  </Text>
                </View>
                <Feather name="arrow-right" size={18} color={colors.textInverse} />
              </View>
              {offer.fine_print ? (
                <Text variant="caption" color="rgba(255,255,255,0.6)" style={styles.finePrint} numberOfLines={1}>
                  {offer.fine_print}
                </Text>
              ) : null}
            </View>
          </Pressable>
        ))}
      </ScrollView>

      {offers.length > 1 ? (
        <View style={styles.dots}>
          {offers.map((o, i) => (
            <View key={o.id} style={[styles.dot, i === active && styles.dotActive]} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingTop: spacing["2xl"] },
  header: { paddingHorizontal: SIDE },
  title: { marginTop: spacing.sm },
  row: { paddingHorizontal: SIDE, paddingTop: spacing.lg },
  card: {
    height: CARD_HEIGHT,
    borderRadius: 22,
    overflow: "hidden",
    backgroundColor: "#143326",
    justifyContent: "space-between",
  },
  badgeRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.md },
  discountBadge: {
    backgroundColor: colors.accent,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
  },
  badgeText: { fontWeight: "800", letterSpacing: 1.4 },
  audienceChip: {
    backgroundColor: "rgba(255,255,255,0.18)",
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm + 2,
    paddingVertical: 4,
  },
  content: { padding: spacing.base },
  offerTitle: { fontSize: 20, lineHeight: 25 },
  offerBody: { marginTop: 4 },
  footerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.md },
  codeChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: "rgba(255,222,162,0.7)",
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
  },
  codeText: { fontSize: 11, letterSpacing: 1.6 },
  finePrint: { marginTop: spacing.sm },
  dots: { flexDirection: "row", justifyContent: "center", gap: 6, marginTop: spacing.base },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: "rgba(255,255,255,0.28)" },
  dotActive: { width: 20, backgroundColor: colors.accent },
});
