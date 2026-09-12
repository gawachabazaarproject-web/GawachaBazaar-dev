import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import { clearTokens, getStoredTokens, saveTokens } from "./tokenStorage";
import { toApiError } from "./errors";

const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL;
if (!BASE_URL) {
  // Fail loudly at startup rather than silently hitting an undefined host -
  // see .env.example for how to configure this per-platform.
  console.warn(
    "[api] EXPO_PUBLIC_API_BASE_URL is not set - requests will fail. See mobile/.env.example.",
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
