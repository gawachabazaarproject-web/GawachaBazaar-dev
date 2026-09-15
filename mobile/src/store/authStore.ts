import { create } from "zustand";
import {
  authApi,
  hydrateAuthTokens,
  setAuthTokens,
  setSessionExpiredHandler,
} from "@/api";
import { queryClient } from "@/api/queryClient";
import { clearTokens, getStoredTokens, saveTokens } from "@/api/tokenStorage";
import { isOtpChallenge, TokenResponse, UserResponse } from "@/types/api";

export type AuthStatus = "restoring" | "authenticated" | "unauthenticated";

/** Result of `login()`: either the login completed outright (a staff
 * account - never expected on this customer-only app, but handled
 * correctly anyway) or an email-OTP challenge must be completed via
 * `verifyOtp` before a session exists. */
export type LoginOutcome =
  | { otpRequired: false }
  | { otpRequired: true; challengeToken: string; maskedEmail: string };

interface AuthState {
  status: AuthStatus;
  user: UserResponse | null;
  sessionExpired: boolean;
  restoreSession: () => Promise<void>;
  login: (identifier: string, password: string) => Promise<LoginOutcome>;
  verifyOtp: (challengeToken: string, code: string) => Promise<void>;
  register: (params: { name: string; email: string; phone: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
  acknowledgeSessionExpired: () => void;
}

async function applySession(result: TokenResponse): Promise<void> {
  await saveTokens({ accessToken: result.access_token, refreshToken: result.refresh_token });
  setAuthTokens({ accessToken: result.access_token, refreshToken: result.refresh_token });
}

export const useAuthStore = create<AuthState>((set, get) => ({
  status: "restoring",
  user: null,
  sessionExpired: false,

  restoreSession: async () => {
    let restored: boolean;
    try {
      restored = await hydrateAuthTokens();
    } catch {
      // A secure-storage read failure should never strand the user on the
      // splash screen forever - fall back to "please log in" like any
      // other missing/invalid session.
      set({ status: "unauthenticated" });
      return;
    }
    if (!restored) {
      set({ status: "unauthenticated" });
      return;
    }
    try {
      const user = await authApi.me();
      set({ status: "authenticated", user });
    } catch {
      // The interceptor already tried refreshing and clearing tokens on
      // failure - just reflect the outcome here. Also clears any
      // in-memory react-query cache (cart, orders, ...) left over from
      // before the app was backgrounded - otherwise a screen like
      // CartBar, which only gates its *query* on auth status, would keep
      // rendering the previous session's stale cached data forever (it
      // never refetches once disabled, so nothing overwrites it).
      queryClient.clear();
      set({ status: "unauthenticated", user: null });
    }
  },

  login: async (identifier, password) => {
    const result = await authApi.login({ identifier, password });
    if (isOtpChallenge(result)) {
      return {
        otpRequired: true,
        challengeToken: result.challenge_token,
        maskedEmail: result.masked_email,
      };
    }
    await applySession(result);
    set({ status: "authenticated", user: result.user, sessionExpired: false });
    return { otpRequired: false };
  },

  verifyOtp: async (challengeToken, code) => {
    const result = await authApi.verifyLoginOtp(challengeToken, code);
    await applySession(result);
    set({ status: "authenticated", user: result.user, sessionExpired: false });
  },

  register: async ({ name, email, phone, password }) => {
    const result = await authApi.register({ name, email, phone, password });
    await applySession(result);
    set({ status: "authenticated", user: result.user, sessionExpired: false });
  },

  logout: async () => {
    const stored = await getStoredTokens();
    if (stored) {
      // Best-effort - a failed server-side revoke should never block the
      // client from forgetting its own tokens.
      await authApi.logout(stored.refreshToken).catch(() => undefined);
    }
    await clearTokens();
    setAuthTokens(null);
    // Every cached query (cart, orders, addresses, ...) belonged to the
    // session that just ended - leaving it in place is what let CartBar
    // keep showing the previous session's item count/total on the login
    // screen (its query is gated on auth status, but a *disabled* query
    // still returns whatever it last fetched; nothing clears that on its
    // own). Also protects the next login on this device, if it's a
    // different account, from briefly seeing this one's cached data.
    queryClient.clear();
    set({ status: "unauthenticated", user: null, sessionExpired: false });
  },

  acknowledgeSessionExpired: () => set({ sessionExpired: false }),
}));

// Wired once, at module load: when the API client exhausts its own
// refresh attempt, it calls this instead of reaching into the store
// directly, keeping src/api/ free of any store dependency.
setSessionExpiredHandler(() => {
  queryClient.clear();
  useAuthStore.setState({ status: "unauthenticated", user: null, sessionExpired: true });
});
