import React, { useCallback, useEffect, useRef, useState } from "react";
import { Linking, Pressable, StyleSheet, useWindowDimensions, View } from "react-native";
import { Image } from "expo-image";
import * as Haptics from "expo-haptics";
import Animated, { useAnimatedScrollHandler, useSharedValue } from "react-native-reanimated";
import { useAds } from "@/features/catalog/useCatalog";
import { colors, radius, spacing } from "@/theme";
import { AdResponse } from "@/types/api";

const SLIDE_HEIGHT = 100;
const AUTO_MS = 4500;

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
  const scrollRef = useRef<Animated.ScrollView>(null);
  const [active, setActive] = useState(0);
  const pausedRef = useRef(false);
  const scrollX = useSharedValue(0);

  const scrollHandler = useAnimatedScrollHandler((event) => {
    scrollX.value = event.contentOffset.x;
  });

  const goTo = useCallback(
    (index: number) => {
      scrollRef.current?.scrollTo({ x: index * slideWidth, animated: true });
      setActive(index);
    },
    [slideWidth]
  );

  useEffect(() => {
    if (!ads || ads.length < 2 || pausedRef.current) return;
    const id = setTimeout(() => goTo((active + 1) % ads.length), AUTO_MS);
    return () => clearTimeout(id);
  }, [active, ads, goTo]);

  const onMomentumEnd = useCallback(
    (e: { nativeEvent: { contentOffset: { x: number } } }) => {
      setActive(Math.round(e.nativeEvent.contentOffset.x / slideWidth));
    },
    [slideWidth]
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
        pagingEnabled
        showsHorizontalScrollIndicator={false}
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
        {ads.map((ad) => (
          <Pressable
            key={ad.id}
            onPress={() => handlePress(ad)}
            style={[styles.slide, { width: slideWidth }]}
            accessibilityRole={ad.link_url ? "button" : undefined}
            accessibilityLabel={`${ad.brand_name} advertisement`}
          >
            <Image source={ad.image_url} style={styles.image} contentFit="cover" transition={150} />
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
  slide: { height: SLIDE_HEIGHT },
  image: {
    width: "100%",
    height: "100%",
    borderRadius: radius.card,
    backgroundColor: colors.background,
  },
  dotRow: {
    flexDirection: "row",
    justifyContent: "center",
    gap: spacing.xs,
    marginTop: spacing.sm,
  },
  dot: { width: 6, height: 6, borderRadius: radius.pill, backgroundColor: colors.divider },
  dotActive: { backgroundColor: colors.primary, width: 16 },
});
