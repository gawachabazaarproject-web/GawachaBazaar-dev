import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Tabs } from "expo-router";
import { BottomTabBarProps } from "@react-navigation/bottom-tabs";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { Text } from "@/components/Text";
import { CartBar } from "@/components/CartBar";
import { colors, spacing } from "@/theme";

const ICONS: Record<string, keyof typeof Feather.glyphMap> = {
  index: "home",
  categories: "grid",
  search: "search",
  orders: "package",
  account: "user",
};

const LABELS: Record<string, string> = {
  index: "Home",
  categories: "Categories",
  search: "Search",
  orders: "Orders",
  account: "Account",
};

function CustomTabBar({ state, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.wrapper, { paddingBottom: insets.bottom }]}>
      <CartBar />
      <View style={styles.tabRow}>
        {state.routes.map((route: (typeof state.routes)[number], index: number) => {
          const focused = state.index === index;
          const color = focused ? colors.primary : colors.textMuted;
          return (
            <Pressable
              key={route.key}
              onPress={() => {
                Haptics.selectionAsync();
                const event = navigation.emit({ type: "tabPress", target: route.key, canPreventDefault: true });
                if (!focused && !event.defaultPrevented) navigation.navigate(route.name);
              }}
              style={styles.tabItem}
              accessibilityRole="button"
              accessibilityLabel={LABELS[route.name] ?? route.name}
              accessibilityState={{ selected: focused }}
            >
              <Feather name={ICONS[route.name] ?? "circle"} size={22} color={color} />
              <Text variant="caption" color={color} style={styles.tabLabel}>
                {LABELS[route.name] ?? route.name}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
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
  wrapper: { backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
  tabRow: { flexDirection: "row", paddingTop: spacing.sm },
  tabItem: { flex: 1, alignItems: "center", gap: 2, paddingBottom: spacing.xs },
  tabLabel: { marginTop: 1 },
});
