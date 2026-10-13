import React, { useEffect } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Tabs } from "expo-router";
import { BottomTabBarProps } from "@react-navigation/bottom-tabs";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import { Text } from "@/components/Text";
import { colors, spacing, timings } from "@/theme";

const ICONS: Record<string, keyof typeof Feather.glyphMap> = {
  index: "home",
  categories: "grid",
  search: "search",
  orders: "package",
  account: "user",
};

const LABELS: Record<string, string> = {
  index: "Home",
  categories: "Shop",
  search: "Search",
  orders: "Orders",
  account: "Account",
};

function CustomTabBar({ state, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.wrapper, { paddingBottom: insets.bottom }]}>
      <View style={styles.tabRow}>
        {state.routes.map((route: (typeof state.routes)[number], index: number) => {
          const focused = state.index === index;
          return (
            <TabBarItem
              key={route.key}
              focused={focused}
              icon={ICONS[route.name] ?? "circle"}
              label={LABELS[route.name] ?? route.name}
              onPress={() => {
                Haptics.selectionAsync();
                const event = navigation.emit({ type: "tabPress", target: route.key, canPreventDefault: true });
                if (!focused && !event.defaultPrevented) navigation.navigate(route.name);
              }}
            />
          );
        })}
      </View>
    </View>
  );
}

function TabBarItem({
  focused,
  icon,
  label,
  onPress,
}: {
  focused: boolean;
  icon: keyof typeof Feather.glyphMap;
  label: string;
  onPress: () => void;
}) {
  const progress = useSharedValue(focused ? 1 : 0);

  useEffect(() => {
    progress.value = withTiming(focused ? 1 : 0, timings.base);
  }, [focused, progress]);

  const indicatorStyle = useAnimatedStyle(() => ({
    opacity: progress.value,
    transform: [{ scaleX: 0.4 + progress.value * 0.6 }],
  }));

  const color = focused ? colors.primary : colors.textMuted;

  return (
    <Pressable
      onPress={onPress}
      style={styles.tabItem}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: focused }}
    >
      <View style={[styles.iconWrap, focused && styles.iconWrapActive]}>
        <Feather name={icon} size={21} color={color} />
      </View>
      <Text variant="label" color={color} style={[styles.tabLabel, focused && styles.tabLabelActive]}>
        {label.toUpperCase()}
      </Text>
      <Animated.View style={[styles.indicator, indicatorStyle]} />
    </Pressable>
  );
}

export default function TabsLayout() {
  return (
    <Tabs tabBar={(props) => <CustomTabBar {...props} />} screenOptions={{ headerShown: false }}>
      <Tabs.Screen name="index" />
      <Tabs.Screen name="categories" />
      <Tabs.Screen name="search" />
      <Tabs.Screen name="orders" />
      <Tabs.Screen name="account" />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    shadowColor: "#000",
    shadowOpacity: 0.06,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: -3 },
    elevation: 8,
  },
  tabRow: { flexDirection: "row", paddingTop: spacing.sm },
  tabItem: { flex: 1, alignItems: "center", gap: 2, paddingBottom: spacing.sm, minHeight: 44 },
  // overflow:hidden guarantees the active highlight renders as a rounded pill.
  iconWrap: { width: 56, height: 34, borderRadius: 17, overflow: "hidden", alignItems: "center", justifyContent: "center" },
  iconWrapActive: { backgroundColor: colors.successLight },
  indicator: { width: 20, height: 3, borderRadius: 2, backgroundColor: colors.accent, marginTop: 1 },
  tabLabel: { marginTop: 1 },
  tabLabelActive: { fontFamily: "PlusJakartaSans_800ExtraBold" },
});
