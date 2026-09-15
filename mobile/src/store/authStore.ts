import { create } from "zustand";
import {
  authApi,
  hydrateAuthTokens,
  setAuthTokens,
  setSessionExpiredHandler,
} from "@/api";
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
      // failure - just reflect the outcome here.
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
    set({ status: "unauthenticated", user: null, sessionExpired: false });
  },

  acknowledgeSessionExpired: () => set({ sessionExpired: false }),
}));

// Wired once, at module load: when the API client exhausts its own
// refresh attempt, it calls this instead of reaching into the store
// directly, keeping src/api/ free of any store dependency.
setSessionExpiredHandler(() => {
  useAuthStore.setState({ status: "unauthenticated", user: null, sessionExpired: true });
});
