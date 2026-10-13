import { useEffect } from "react";
import { Platform } from "react-native";
import * as Notifications from "expo-notifications";
import Constants from "expo-constants";
import { useRouter } from "expo-router";
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
export function usePushNotifications(): void {
  const status = useAuthStore((s) => s.status);
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (status !== "authenticated") return;
    let cancelled = false;
    registerForPush()
      .then(async (token) => {
        if (!token || cancelled) return;
        await pushApi.register(token, Platform.OS);
        registeredToken = token;
      })
      .catch(() => undefined); // Push is optional; never block the app on it.
    return () => {
      cancelled = true;
    };
  }, [status]);

  useEffect(() => {
    const received = Notifications.addNotificationReceivedListener((n) => {
      const orderId = n.request.content.data?.orderId;
      if (orderId) void queryClient.invalidateQueries({ queryKey: ["order", orderId] });
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
    });
    const open = (response: Notifications.NotificationResponse | null) => {
      const orderId = response?.notification.request.content.data?.orderId;
      if (orderId) router.push(`/order/${orderId}` as never);
    };
    // Tap that cold-started the app.
    open(Notifications.getLastNotificationResponse());
    const tapped = Notifications.addNotificationResponseReceivedListener(open);
    return () => {
      received.remove();
      tapped.remove();
    };
  }, [router, queryClient]);
}

/** Call before signing out, while the auth token is still valid, so this
 * device stops receiving the previous account's notifications. */
export async function unregisterPushToken(): Promise<void> {
  if (!registeredToken) return;
  const token = registeredToken;
  registeredToken = null;
  await pushApi.unregister(token).catch(() => undefined);
}
