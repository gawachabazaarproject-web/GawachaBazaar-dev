import { useEffect, useState } from "react";
import { Platform } from "react-native";
import * as Notifications from "expo-notifications";
import Constants from "expo-constants";
import { useRootNavigationState, useRouter, useSegments } from "expo-router";
import { notificationRoute } from "./notificationRouting";
import { useQueryClient } from "@tanstack/react-query";
import { pushApi } from "@/api";
import { useAuthStore } from "@/store/authStore";

// Show alerts while the app is open too (order updates are the point).
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

let registeredToken: string | null = null;

async function registerForPush(): Promise<string | null> {
  if (Platform.OS === "web") return null;
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("orders", {
      name: "Order updates",
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
    });
  }
  const existing = await Notifications.getPermissionsAsync();
  let granted = existing.granted;
  if (!granted && existing.canAskAgain) {
    granted = (await Notifications.requestPermissionsAsync()).granted;
  }
  if (!granted) return null;
  const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
  const { data } = await Notifications.getExpoPushTokenAsync(projectId ? { projectId } : undefined);
  return data;
}

/** Registers this device's push token with the backend once signed in, and
 * routes notification taps to the order they're about. Mounted once at the
 * app root (see PushNotifications in app/_layout.tsx). */
// Tap identifiers already acted on, so a remount never replays the cold-start tap.
const handledTaps = new Set<string>();

export function usePushNotifications(): void {
  const status = useAuthStore((s) => s.status);
  const router = useRouter();
  const segments = useSegments();
  const navReady = !!useRootNavigationState()?.key;
  const queryClient = useQueryClient();
  const [pendingRoute, setPendingRoute] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated") return;
    let cancelled = false;
    const register = (token: string) =>
      pushApi.register(token, Platform.OS).then(() => {
        registeredToken = token;
      });
    registerForPush()
      .then(async (token) => {
        if (!token || cancelled) return;
        await register(token);
      })
      .catch(() => undefined); // Push is optional; never block the app on it.
    // Expo/FCM can rotate the token while the app is installed; keep the backend current.
    const rotated = Notifications.addPushTokenListener((t) => {
      if (typeof t.data === "string" && t.data.startsWith("Expo")) void register(t.data).catch(() => undefined);
    });
    return () => {
      cancelled = true;
      rotated.remove();
    };
  }, [status]);

  useEffect(() => {
    const received = Notifications.addNotificationReceivedListener((n) => {
      const orderId = n.request.content.data?.orderId;
      if (orderId) void queryClient.invalidateQueries({ queryKey: ["order", orderId] });
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
    });
    // Only record the target here; navigating is the job of the effect below,
    // which waits until the session is restored and the navigator is mounted.
    const open = (response: Notifications.NotificationResponse | null) => {
      if (!response) return;
      const id = response.notification.request.identifier;
      if (handledTaps.has(id)) return;
      handledTaps.add(id);
      const route = notificationRoute(response.notification.request.content.data);
      if (route) setPendingRoute(route);
    };
    // Tap that cold-started the app.
    open(Notifications.getLastNotificationResponse());
    const tapped = Notifications.addNotificationResponseReceivedListener(open);
    return () => {
      received.remove();
      tapped.remove();
    };
  }, [queryClient]);

  useEffect(() => {
    if (!pendingRoute || !navReady) return;
    // Logged-out user: nothing to open (their order is not theirs to see here); drop the tap.
    if (status === "unauthenticated") {
      setPendingRoute(null);
      return;
    }
    // Wait for AppGate to finish its redirects (login/onboarding -> tabs).
    const group = segments[0] as string | undefined;
    if (status !== "authenticated" || group === "(auth)" || group === "(onboarding)") return;
    setPendingRoute(null);
    router.push(pendingRoute as never);
  }, [pendingRoute, navReady, status, segments, router]);
}

/** Call before signing out, while the auth token is still valid, so this
 * device stops receiving the previous account's notifications. */
export async function unregisterPushToken(): Promise<void> {
  if (!registeredToken) return;
  const token = registeredToken;
  registeredToken = null;
  await pushApi.unregister(token).catch(() => undefined);
}
