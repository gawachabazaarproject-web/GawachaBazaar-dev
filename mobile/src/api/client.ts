import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import Constants from "expo-constants";
import { clearTokens, getStoredTokens, saveTokens } from "./tokenStorage";
import { toApiError } from "./errors";

const BACKEND_PORT = 8000;

/**
 * Resolves the backend's base URL by reusing the exact host Expo Go/the
 * dev client already used to reach Metro (`Constants.expoConfig.hostUri`)
 * - whatever that is (a LAN IP, 10.0.2.2, localhost), it's guaranteed
 * reachable right now, and it self-heals across DHCP/network changes.
 * A hardcoded EXPO_PUBLIC_API_BASE_URL goes stale the moment the dev
 * machine's IP changes, which is exactly what broke LAN testing here.
 *
 * Falls back to EXPO_PUBLIC_API_BASE_URL when there's no dev-server host
 * to derive from (a production/standalone build, or web).
 */
function resolveBaseUrl(): string {
  const hostUri = Constants.expoConfig?.hostUri;
  const host = hostUri?.split(":")[0];
  if (host) return `http://${host}:${BACKEND_PORT}/api/v1`;
  return process.env.EXPO_PUBLIC_API_BASE_URL ?? "";
}

const BASE_URL = resolveBaseUrl();
if (!BASE_URL) {
  // Fail loudly at startup rather than silently hitting an undefined host -
  // see .env.example for how to configure this per-platform.
  console.warn(
    "[api] Could not resolve an API base URL - requests will fail. See mobile/.env.example.",
  );
}

/** In-memory copy of the access token, kept in sync with secure storage.
 * Reading secure storage on every single request would be needless async
 * overhead; this is the one place that cache lives. */
let accessToken: string | null = null;
let refreshToken: string | null = null;

/** Registered by the auth store so the client can react to an
 * unrecoverable session expiry (refresh itself failed) without the API
 * layer needing to know about navigation/store internals. */
let onSessionExpired: (() => void) | null = null;
export function setSessionExpiredHandler(handler: (() => void) | null): void {
  onSessionExpired = handler;
}

export function setAuthTokens(tokens: { accessToken: string; refreshToken: string } | null): void {
  accessToken = tokens?.accessToken ?? null;
  refreshToken = tokens?.refreshToken ?? null;
}

/** Current in-memory access token, for the one caller that can't go
 * through `apiClient`'s own interceptor - the realtime WebSocket, which
 * needs the token as a query param at connect time (see
 * useRealtimeSync.ts and backend/app/api/v1/realtime.py for why). */
export function getAccessToken(): string | null {
  return accessToken;
}

/** Same host/port `apiClient` resolved to, swapped to the ws(s) scheme -
 * a browser/RN WebSocket can't set the Authorization header a real
 * request would, so the token travels as a query param instead. */
export function getRealtimeUrl(token: string): string {
  return `${BASE_URL.replace(/^http/, "ws")}/ws/events?token=${encodeURIComponent(token)}`;
}

/** Call once at app startup, before rendering, to hydrate the in-memory
 * tokens from secure storage. Returns true if a session was restored. */
export async function hydrateAuthTokens(): Promise<boolean> {
  const stored = await getStoredTokens();
  if (!stored) return false;
  setAuthTokens(stored);
  return true;
}

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
});

const AUTH_EXEMPT_PATHS = ["/auth/login", "/auth/register", "/auth/refresh"];

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const isExempt = AUTH_EXEMPT_PATHS.some((p) => config.url?.includes(p));
  if (accessToken && !isExempt) {
    config.headers.set("Authorization", `Bearer ${accessToken}`);
  }
  return config;
});

/** Single-flight refresh: concurrent 401s while a refresh is already in
 * flight all await the SAME promise instead of each firing their own
 * refresh request. */
let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  if (!refreshToken) throw new Error("No refresh token available");
  if (!refreshPromise) {
    refreshPromise = axios
      .post(`${BASE_URL}/auth/refresh`, { refresh_token: refreshToken })
      .then(async (res) => {
        const { access_token, refresh_token } = res.data;
        await saveTokens({ accessToken: access_token, refreshToken: refresh_token });
        setAuthTokens({ accessToken: access_token, refreshToken: refresh_token });
        return access_token as string;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    const status = error.response?.status;
    const isExempt = AUTH_EXEMPT_PATHS.some((p) => original?.url?.includes(p));

    if (status === 401 && original && !original._retried && !isExempt && refreshToken) {
      original._retried = true;
      try {
        const newAccessToken = await refreshAccessToken();
        original.headers.set("Authorization", `Bearer ${newAccessToken}`);
        return apiClient.request(original);
      } catch {
        await clearTokens();
        setAuthTokens(null);
        onSessionExpired?.();
        return Promise.reject(toApiError(error));
      }
    }

    if (status === 401 && (isExempt || !refreshToken)) {
      // A 401 on login/register/refresh itself, or with nothing to refresh
      // with - this is an unrecoverable auth failure, not a
      // token-expiry-mid-session case.
      if (!isExempt) {
        await clearTokens();
        setAuthTokens(null);
        onSessionExpired?.();
      }
    }

    return Promise.reject(toApiError(error));
  },
);
