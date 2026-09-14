import React, { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, useWindowDimensions, View } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import Animated, {
  SharedValue,
  Extrapolation,
  interpolate,
  useAnimatedScrollHandler,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";
import { Text } from "../Text";
import { CAMPAIGN_SLIDES } from "@/utils/campaignSlides";
import { colors, radius, spacing } from "@/theme";

const SLIDE_HEIGHT = 480;
const POSTER_RADIUS = 20;
const AUTO_MS = 5500;

export interface PromoCarouselProps {
  onSlidePress?: (slideId: string) => void;
}

/**
 * Cinematic promotional carousel - the home screen's opening statement.
 * Full-bleed campaign-poster slides (image + editorial label + large
 * serif headline with an italic accent word + short body + CTA), with a
 * scroll-driven parallax/scale/opacity transition between slides and a
 * HubSpec-style auto-advancing progress dot row.
 */
export function PromoCarousel({ onSlidePress }: PromoCarouselProps) {
  const { width: SLIDE_WIDTH } = useWindowDimensions();
  const scrollX = useSharedValue(0);
  const dotProgress = useSharedValue(0);
  const scrollRef = useRef<Animated.ScrollView>(null);
  const [active, setActive] = useState(0);
  const pausedRef = useRef(false);

  const scrollHandler = useAnimatedScrollHandler((event) => {
    scrollX.value = event.contentOffset.x;
  });

  const restartProgress = useCallback(() => {
    dotProgress.value = 0;
    dotProgress.value = withTiming(1, { duration: AUTO_MS });
  }, [dotProgress]);

  const goTo = useCallback(
    (index: number) => {
      scrollRef.current?.scrollTo({ x: index * SLIDE_WIDTH, animated: true });
      setActive(index);
      restartProgress();
    },
    [restartProgress]
  );

  useEffect(() => {
    restartProgress();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (pausedRef.current) return;
    const id = setTimeout(() => {
      goTo((active + 1) % CAMPAIGN_SLIDES.length);
    }, AUTO_MS);
    return () => clearTimeout(id);
  }, [active, goTo]);

  const onMomentumEnd = useCallback(
    (e: { nativeEvent: { contentOffset: { x: number } } }) => {
      const index = Math.round(e.nativeEvent.contentOffset.x / SLIDE_WIDTH);
      setActive(index);
      restartProgress();
    },
    [restartProgress]
  );

  return (
    <View style={styles.wrap}>
      <Animated.ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onScroll={scrollHandler}
        scrollEventThrottle={16}
        onScrollBeginDrag={() => {
          pausedRef.current = true;
        }}
        onMomentumScrollEnd={(e) => {
          pausedRef.current = false;
          onMomentumEnd(e);
        }}
      >
        {CAMPAIGN_SLIDES.map((slide, i) => (
          <Slide
            key={slide.id}
            slide={slide}
            index={i}
            slideWidth={SLIDE_WIDTH}
            scrollX={scrollX}
            onPress={() => onSlidePress?.(slide.id)}
          />
        ))}
      </Animated.ScrollView>

      <View style={styles.indicatorRow}>
        {CAMPAIGN_SLIDES.map((slide, i) => (
          <Pressable
            key={slide.id}
            onPress={() => {
              Haptics.selectionAsync().catch(() => undefined);
              goTo(i);
            }}
            style={[styles.dot, i === active && styles.dotActive]}
          >
            {i === active ? <DotFill progress={dotProgress} /> : null}
          </Pressable>
        ))}
        <Text variant="eyebrow" color="rgba(255,255,255,0.5)" style={styles.counter}>
          {String(active + 1).padStart(2, "0")} / {String(CAMPAIGN_SLIDES.length).padStart(2, "0")}
        </Text>
      </View>
    </View>
  );
}

function DotFill({ progress }: { progress: SharedValue<number> }) {
  const style = useAnimatedStyle(() => ({ width: `${progress.value * 100}%` }));
  return <Animated.View style={[styles.dotFill, style]} />;
}

function Slide({
  slide,
  index,
  slideWidth,
  scrollX,
  onPress,
}: {
  slide: (typeof CAMPAIGN_SLIDES)[number];
  index: number;
  slideWidth: number;
  scrollX: SharedValue<number>;
  onPress: () => void;
}) {
  const inputRange = [(index - 1) * slideWidth, index * slideWidth, (index + 1) * slideWidth];

  const imageStyle = useAnimatedStyle(() => ({
    transform: [
      { scale: interpolate(scrollX.value, inputRange, [1.18, 1, 1.18], Extrapolation.CLAMP) },
      { translateX: interpolate(scrollX.value, inputRange, [-30, 0, 30], Extrapolation.CLAMP) },
    ],
  }));

  const textStyle = useAnimatedStyle(() => ({
    opacity: interpolate(scrollX.value, inputRange, [0, 1, 0], Extrapolation.CLAMP),
    transform: [{ translateY: interpolate(scrollX.value, inputRange, [24, 0, -12], Extrapolation.CLAMP) }],
  }));

  const labelStyle = useAnimatedStyle(() => ({
    opacity: interpolate(scrollX.value, inputRange, [0, 1, 0], Extrapolation.CLAMP),
    transform: [{ translateY: interpolate(scrollX.value, inputRange, [12, 0, -6], Extrapolation.CLAMP) }],
  }));

  return (
    <Pressable onPress={onPress} style={[styles.slide, { width: slideWidth }]}>
      <View style={styles.poster}>
        <Animated.View style={[StyleSheet.absoluteFill, imageStyle]}>
          <Image source={slide.image} style={StyleSheet.absoluteFill} contentFit="cover" />
        </Animated.View>
        <LinearGradient
          pointerEvents="none"
          colors={[
            "rgba(6,26,18,0)",
            "rgba(6,26,18,0.14)",
            "rgba(6,26,18,0.55)",
            "rgba(6,26,18,0.82)",
            "rgba(6,26,18,0.97)",
          ]}
          locations={[0, 0.38, 0.62, 0.82, 1]}
          style={StyleSheet.absoluteFill}
        />
        <View style={styles.content}>
          <Animated.View style={labelStyle}>
            <Text variant="eyebrow" color={colors.accentLight}>
              {String(index + 1).padStart(2, "0")} / {String(CAMPAIGN_SLIDES.length).padStart(2, "0")} — {slide.label}
            </Text>
          </Animated.View>
          <Animated.View style={textStyle}>
            <Text variant="displayXL" color={colors.textInverse} style={styles.title}>
              {slide.title}
              {slide.scriptSuffix ? (
                <Text variant="scriptLarge" color={colors.accentLight}>
                  {"\n"}
                  {slide.scriptSuffix}
                </Text>
              ) : null}
            </Text>
            <Text variant="body" color="rgba(255,255,255,0.8)" style={styles.body} numberOfLines={2}>
              {slide.body}
            </Text>
            <View style={styles.cta}>
              <Text variant="eyebrow" color={colors.textInverse}>
                {slide.ctaLabel.toUpperCase()}
              </Text>
              <Feather name="arrow-right" size={14} color={colors.textInverse} />
            </View>
          </Animated.View>
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: { height: SLIDE_HEIGHT, backgroundColor: colors.background },
  slide: {
    height: SLIDE_HEIGHT,
    backgroundColor: colors.background,
    paddingHorizontal: spacing.base,
  },
  poster: {
    flex: 1,
    borderRadius: POSTER_RADIUS,
    overflow: "hidden",
    backgroundColor: colors.primary,
  },
  content: {
    position: "absolute",
    left: spacing.lg,
    right: spacing.lg,
    bottom: spacing.xl,
  },
  title: { marginTop: spacing.md },
  body: { marginTop: spacing.lg, maxWidth: "80%" },
  cta: {
    marginTop: spacing.xl,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    alignSelf: "flex-start",
    borderBottomWidth: 1,
    borderColor: "rgba(255,255,255,0.4)",
    paddingBottom: spacing.xs,
  },
  indicatorRow: {
    position: "absolute",
    left: spacing.base + spacing.lg,
    right: spacing.base + spacing.lg,
    bottom: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  dot: {
    height: 3,
    width: 16,
    borderRadius: radius.none,
    backgroundColor: "rgba(255,255,255,0.3)",
    overflow: "hidden",
  },
  dotActive: { width: 28 },
  dotFill: { height: "100%", width: "100%", backgroundColor: colors.accent },
  counter: { marginLeft: "auto" },
});
