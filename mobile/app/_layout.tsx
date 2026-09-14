import "react-native-gesture-handler";
import React, { useEffect } from "react";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClientProvider } from "@tanstack/react-query";
import { Stack, SplashScreen } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useFonts, NotoSerif_600SemiBold, NotoSerif_700Bold } from "@expo-google-fonts/noto-serif";
import {
  PlusJakartaSans_400Regular,
  PlusJakartaSans_500Medium,
  PlusJakartaSans_600SemiBold,
  PlusJakartaSans_700Bold,
} from "@expo-google-fonts/plus-jakarta-sans";
import { queryClient } from "@/api/queryClient";
import { useAuthStore } from "@/store/authStore";
import { ToastHost } from "@/components/ToastHost";
import { CartBar } from "@/components/CartBar";
import { AppGate } from "@/navigation/AppGate";

SplashScreen.preventAutoHideAsync().catch(() => undefined);

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    NotoSerif_600SemiBold,
    NotoSerif_700Bold,
    PlusJakartaSans_400Regular,
    PlusJakartaSans_500Medium,
    PlusJakartaSans_600SemiBold,
    PlusJakartaSans_700Bold,
  });
  const restoreSession = useAuthStore((s) => s.restoreSession);
  const authStatus = useAuthStore((s) => s.status);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  const appReady = fontsLoaded && authStatus !== "restoring";

  useEffect(() => {
    if (appReady) {
      SplashScreen.hideAsync().catch(() => undefined);
    }
  }, [appReady]);

  if (!appReady) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <StatusBar style="dark" />
          <AppGate>
            <Stack screenOptions={{ headerShown: false }}>
              <Stack.Screen name="(auth)" />
              <Stack.Screen name="(onboarding)" />
              <Stack.Screen name="(tabs)" />
              <Stack.Screen name="product/[id]" options={{ presentation: "card" }} />
              <Stack.Screen name="category/[id]" options={{ presentation: "card" }} />
              <Stack.Screen name="cart/index" options={{ presentation: "modal" }} />
              <Stack.Screen name="checkout/index" options={{ presentation: "card" }} />
              <Stack.Screen name="checkout/success" options={{ presentation: "fullScreenModal", gestureEnabled: false }} />
              <Stack.Screen name="order/[id]/index" options={{ presentation: "card" }} />
              <Stack.Screen name="order/[id]/cancel" options={{ presentation: "modal" }} />
              <Stack.Screen name="order/[id]/refund" options={{ presentation: "card" }} />
              <Stack.Screen name="address/index" options={{ presentation: "card" }} />
              <Stack.Screen name="address/add" options={{ presentation: "modal" }} />
              <Stack.Screen name="address/edit/[id]" options={{ presentation: "modal" }} />
              <Stack.Screen name="account/profile" options={{ presentation: "card" }} />
              <Stack.Screen name="account/support" options={{ presentation: "card" }} />
              <Stack.Screen name="account/settings" options={{ presentation: "card" }} />
            </Stack>
            <CartBar />
            <ToastHost />
          </AppGate>
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
