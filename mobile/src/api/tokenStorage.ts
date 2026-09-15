import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

/**
 * The only place access/refresh tokens touch disk. On iOS/Android this uses
 * Keychain / EncryptedSharedPreferences-backed Keystore via
 * expo-secure-store - never AsyncStorage, which is plain-text on Android.
 *
 * `expo-secure-store` has no web implementation at all (its methods throw
 * "not available on web" there) - confirmed live while testing the
 * Promotions checkout flow against the web preview target: login succeeded
 * against the backend, then this module's save step threw and the whole
 * login appeared to silently fail. `localStorage` is the standard Expo
 * fallback for the web target only; native builds are unaffected and keep
 * using SecureStore exactly as before.
 */
const ACCESS_TOKEN_KEY = "gawachabazaar.access_token";
const REFRESH_TOKEN_KEY = "gawachabazaar.refresh_token";

export interface StoredTokens {
  accessToken: string;
  refreshToken: string;
}

async function setItem(key: string, value: string): Promise<void> {
  if (Platform.OS === "web") {
    window.localStorage.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

async function getItem(key: string): Promise<string | null> {
  if (Platform.OS === "web") {
    return window.localStorage.getItem(key);
  }
  return SecureStore.getItemAsync(key);
}

async function deleteItem(key: string): Promise<void> {
  if (Platform.OS === "web") {
    window.localStorage.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
}

export async function saveTokens(tokens: StoredTokens): Promise<void> {
  await Promise.all([
    setItem(ACCESS_TOKEN_KEY, tokens.accessToken),
    setItem(REFRESH_TOKEN_KEY, tokens.refreshToken),
  ]);
}

export async function getStoredTokens(): Promise<StoredTokens | null> {
  const [accessToken, refreshToken] = await Promise.all([
    getItem(ACCESS_TOKEN_KEY),
    getItem(REFRESH_TOKEN_KEY),
  ]);
  if (!accessToken || !refreshToken) return null;
  return { accessToken, refreshToken };
}

export async function clearTokens(): Promise<void> {
  await Promise.all([deleteItem(ACCESS_TOKEN_KEY), deleteItem(REFRESH_TOKEN_KEY)]);
}
