import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import Constants from "expo-constants";
import { getIdToken } from "@/auth/firebase";
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
  // Optional: force a dev build onto another backend (e.g. the deployed one,
  // which sits next to its database and is far faster than a laptop backend
  // talking to a remote DB). Unset = the normal Metro-host behaviour below.
  const override = process.env.EXPO_PUBLIC_API_URL_OVERRIDE;
  if (override) return override;
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

/**
 * Auth: every request carries the current Firebase ID token as its Bearer
 * token. The Firebase SDK caches it and refreshes it shortly before its
 * one-hour expiry, so there is no refresh-token handling here - the SDK
 * persists the session itself (Keychain/Keystore natively, IndexedDB on web).
 */

/** Last token handed out - for the realtime WebSocket, which needs a
 * token synchronously as a query param (see useRealtimeSync.ts). */
let lastToken: string | null = null;

/** Registered by the auth store: how to react when the backend rejects an
 * otherwise-valid sign-in (account disabled, email not verified, ...),
 * without src/api/ depending on the store. */
type AuthFailureHandler = (code: string) => void;
let onAuthFailure: AuthFailureHandler | null = null;
export function setAuthFailureHandler(handler: AuthFailureHandler | null): void {
  onAuthFailure = handler;
}

export function getAccessToken(): string | null {
  return lastToken;
}

/** Fresh token for callers outside apiClient (realtime reconnects). */
export async function fetchAccessToken(): Promise<string | null> {
  lastToken = await getIdToken();
  return lastToken;
}

/** Same host/port `apiClient` resolved to, swapped to the ws(s) scheme -
 * a browser/RN WebSocket can't set the Authorization header a real
 * request would, so the token travels as a query param instead. */
export function getRealtimeUrl(token: string): string {
  return `${BASE_URL.replace(/^http/, "ws")}/ws/events?token=${encodeURIComponent(token)}`;
}

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
});

/** Fire-and-forget ping to the dependency-free /health route so a sleeping
 * host (Render's free tier spins down when idle) starts waking while the
 * splash screen and font load run, instead of on the first real request. */
export function warmBackend(): void {
  if (!BASE_URL) return;
  const root = BASE_URL.replace(/\/api\/v1\/?$/, "");
  axios.get(`${root}/health`, { timeout: 60000 }).catch(() => undefined);
}

/** No Bearer token: the pre-Firebase account migration is anonymous. */
const AUTH_EXEMPT_PATHS = ["/auth/legacy-migrate"];

apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const isExempt = AUTH_EXEMPT_PATHS.some((p) => config.url?.includes(p));
  if (!isExempt) {
    const token = await getIdToken().catch(() => null);
    lastToken = token;
    if (token) config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ code?: string }>) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    const status = error.response?.status;
    const code = error.response?.data?.code;

    // Token expired between the SDK's cached check and the server's: force
    // a refresh once and retry.
    if (status === 401 && code === "TOKEN_EXPIRED" && original && !original._retried) {
      original._retried = true;
      const token = await getIdToken(true).catch(() => null);
      if (token) {
        lastToken = token;
        original.headers.set("Authorization", `Bearer ${token}`);
        return apiClient.request(original);
      }
    }

    const isAuthPath = original?.url?.includes("/auth/");
    if (code && !isAuthPath && (status === 401 || code === "EMAIL_NOT_VERIFIED")) {
      onAuthFailure?.(code);
    }
    return Promise.reject(toApiError(error));
  },
);
