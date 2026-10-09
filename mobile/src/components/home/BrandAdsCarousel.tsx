import React, { useCallback, useEffect, useRef, useState } from "react";
import { Linking, Pressable, StyleSheet, useWindowDimensions, View } from "react-native";
import { Image } from "expo-image";
import * as Haptics from "expo-haptics";
import { Feather } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import Animated, { useAnimatedScrollHandler, useSharedValue } from "react-native-reanimated";
import { Text } from "@/components/Text";
import { useAds } from "@/features/catalog/useCatalog";
import { colors, radius, spacing } from "@/theme";
import { AdResponse } from "@/types/api";

/** Ad creatives must be 12:5 (recommended 1200x500 px). The slide keeps that
 * exact ratio on every screen width, so a correctly sized image is never
 * cropped. Keep in sync with AD_IMAGE in Admin/lib/ads.ts. */
const SLIDE_ASPECT_RATIO = 12 / 5;
const AUTO_MS = 4500;
/** Visible gap between neighbouring ad cards; the strip snaps card by card. */
const CARD_GAP = spacing.md;

/**
 * Small rectangular brand-ads strip - sits below the regular/wholesale
 * toggle on Home. Deliberately compact and understated next to
 * PromoCarousel's full-bleed cinematic hero above it: this is paid
 * third-party brand placement, not the app's own editorial voice. Real
 * ads only (see AdService.list_active_ads/GET /ads) - renders nothing
 * when there are none, never a placeholder banner.
 */
export function BrandAdsCarousel() {
  const { data: ads } = useAds();
  const { width: screenWidth } = useWindowDimensions();
  const slideWidth = screenWidth - spacing.base * 2;
  const stride = slideWidth + CARD_GAP;
  const scrollRef = useRef<Animated.ScrollView>(null);
  const [active, setActive] = useState(0);
  const pausedRef = useRef(false);
  const scrollX = useSharedValue(0);

  const scrollHandler = useAnimatedScrollHandler((event) => {
    scrollX.value = event.contentOffset.x;
  });

  const goTo = useCallback(
    (index: number) => {
      scrollRef.current?.scrollTo({ x: index * stride, animated: true });
      setActive(index);
    },
    [stride]
  );

  useEffect(() => {
    if (!ads || ads.length < 2 || pausedRef.current) return;
    const id = setTimeout(() => goTo((active + 1) % ads.length), AUTO_MS);
    return () => clearTimeout(id);
  }, [active, ads, goTo]);

  const onMomentumEnd = useCallback(
    (e: { nativeEvent: { contentOffset: { x: number } } }) => {
      setActive(Math.round(e.nativeEvent.contentOffset.x / stride));
    },
    [stride]
  );

  const handlePress = (ad: AdResponse) => {
    if (!ad.link_url) return;
    Linking.openURL(ad.link_url).catch(() => undefined);
  };

  if (!ads || ads.length === 0) return null;

  return (
    <View style={styles.wrap}>
      <Animated.ScrollView
        ref={scrollRef}
        horizontal
        snapToInterval={stride}
        decelerationRate="fast"
        showsHorizontalScrollIndicator={false}
        scrollEnabled={ads.length > 1}
        onScroll={scrollHandler}
        scrollEventThrottle={16}
        contentContainerStyle={{ paddingHorizontal: spacing.base }}
        onScrollBeginDrag={() => {
          pausedRef.current = true;
        }}
        onMomentumScrollEnd={(e) => {
          pausedRef.current = false;
          onMomentumEnd(e);
        }}
      >
        {ads.map((ad, index) => (
          <Pressable
            key={ad.id}
            onPress={() => handlePress(ad)}
            style={[styles.slide, { width: slideWidth, marginRight: index < ads.length - 1 ? CARD_GAP : 0 }]}
            accessibilityRole={ad.link_url ? "button" : undefined}
            accessibilityLabel={`${ad.brand_name} advertisement`}
          >
            <Image source={ad.image_url} style={styles.image} contentFit="cover" transition={150} />
            <LinearGradient
              colors={["rgba(6,26,18,0)", "rgba(6,26,18,0.9)"]}
              style={styles.textWrap}
              pointerEvents="none"
            >
              <View style={styles.textLeft}>
                {ad.title ? (
                  <Text variant="eyebrow" color={colors.accentLight} numberOfLines={1}>
                    {ad.title.toUpperCase()}
                  </Text>
                ) : null}
                <Text variant="displayM" color={colors.textInverse} numberOfLines={1} style={styles.brand}>
                  {ad.brand_name}
                </Text>
                {ad.subtitle ? (
                  <Text variant="bodySmall" color="rgba(255,255,255,0.8)" numberOfLines={1} style={styles.subtitle}>
                    {ad.subtitle}
                  </Text>
                ) : null}
              </View>
              {ad.link_url ? (
                <View style={styles.seeMore}>
                  <Text variant="eyebrow" color={colors.textInverse}>
                    SEE MORE
                  </Text>
                  <Feather name="arrow-right" size={14} color={colors.textInverse} />
                </View>
              ) : null}
            </LinearGradient>
          </Pressable>
        ))}
      </Animated.ScrollView>

      {ads.length > 1 ? (
        <View style={styles.dotRow}>
          {ads.map((ad, i) => (
            <Pressable
              key={ad.id}
              onPress={() => {
                Haptics.selectionAsync().catch(() => undefined);
                goTo(i);
              }}
              style={[styles.dot, i === active && styles.dotActive]}
            />
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: spacing.lg, marginBottom: spacing.xl },
  slide: { aspectRatio: SLIDE_ASPECT_RATIO },
  image: {
    width: "100%",
    height: "100%",
    borderRadius: radius.card,
    backgroundColor: colors.background,
  },
  textWrap: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: spacing.base,
    paddingTop: spacing["2xl"],
    paddingBottom: spacing.md,
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: spacing.sm,
    borderBottomLeftRadius: radius.card,
    borderBottomRightRadius: radius.card,
  },
  textLeft: { flex: 1 },
  seeMore: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    borderBottomWidth: 1,
    borderColor: "rgba(255,255,255,0.4)",
    paddingBottom: 2,
  },
  brand: { marginTop: 2 },
  subtitle: { marginTop: 2, opacity: 0.92 },
  dotRow: {
    flexDirection: "row",
    justifyContent: "center",
    gap: spacing.xs,
    marginTop: spacing.sm,
  },
  dot: { width: 6, height: 6, borderRadius: radius.pill, backgroundColor: colors.divider },
  dotActive: { backgroundColor: colors.primary, width: 16 },
});
