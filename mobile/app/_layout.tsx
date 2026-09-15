import "react-native-gesture-handler";
import React, { useEffect } from "react";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryClientProvider } from "@tanstack/react-query";
import { Stack, SplashScreen } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useFonts } from "expo-font";
import {
  BodoniModa_400Regular,
  BodoniModa_500Medium,
  BodoniModa_600SemiBold,
  BodoniModa_700Bold,
  BodoniModa_800ExtraBold,
  BodoniModa_400Regular_Italic,
  BodoniModa_600SemiBold_Italic,
} from "@expo-google-fonts/bodoni-moda";
import { InstrumentSerif_400Regular, InstrumentSerif_400Regular_Italic } from "@expo-google-fonts/instrument-serif";
import {
  PlusJakartaSans_400Regular,
  PlusJakartaSans_500Medium,
  PlusJakartaSans_600SemiBold,
  PlusJakartaSans_700Bold,
  PlusJakartaSans_800ExtraBold,
} from "@expo-google-fonts/plus-jakarta-sans";
import { Baloo2_500Medium, Baloo2_600SemiBold, Baloo2_700Bold } from "@expo-google-fonts/baloo-2";
import { ReducedMotionConfig, ReduceMotion } from "react-native-reanimated";
import { queryClient } from "@/api/queryClient";
import { useAuthStore } from "@/store/authStore";
import { ToastHost } from "@/components/ToastHost";
import { CartBar } from "@/components/CartBar";
import { BulkRequestBar } from "@/components/home/BulkRequestBar";
import { AppGate } from "@/navigation/AppGate";
import { useRealtimeSync } from "@/features/orders/useRealtimeSync";

SplashScreen.preventAutoHideAsync().catch(() => undefined);

/** No-UI side-effect component (same shape as AppGate) - exists only
 * because useRealtimeSync needs useQueryClient(), which requires being a
 * descendant of QueryClientProvider in the rendered tree, not just
 * textually nested under it in RootLayout's own return statement. */
function RealtimeSync(): null {
  useRealtimeSync();
  return null;
}

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    BodoniModa_400Regular,
    BodoniModa_500Medium,
    BodoniModa_600SemiBold,
    BodoniModa_700Bold,
    BodoniModa_800ExtraBold,
    BodoniModa_400Regular_Italic,
    BodoniModa_600SemiBold_Italic,
    InstrumentSerif_400Regular,
    InstrumentSerif_400Regular_Italic,
    PlusJakartaSans_400Regular,
    PlusJakartaSans_500Medium,
    PlusJakartaSans_600SemiBold,
    PlusJakartaSans_700Bold,
    PlusJakartaSans_800ExtraBold,
    Baloo2_500Medium,
    Baloo2_600SemiBold,
    Baloo2_700Bold,
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
      <ReducedMotionConfig mode={ReduceMotion.System} />
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <StatusBar style="dark" />
          <RealtimeSync />
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
              <Stack.Screen name="bulk/review" options={{ presentation: "modal" }} />
              <Stack.Screen name="bulk/success" options={{ presentation: "fullScreenModal", gestureEnabled: false }} />
              <Stack.Screen name="bulk/requests" options={{ presentation: "card" }} />
              <Stack.Screen name="bulk/[id]" options={{ presentation: "card" }} />
            </Stack>
            <CartBar />
            <BulkRequestBar />
            <ToastHost />
          </AppGate>
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
