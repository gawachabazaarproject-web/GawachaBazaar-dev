import { create } from "zustand";
import {
  authApi,
  hydrateAuthTokens,
  setAuthTokens,
  setSessionExpiredHandler,
} from "@/api";
import { clearTokens, getStoredTokens, saveTokens } from "@/api/tokenStorage";
import { UserResponse } from "@/types/api";

export type AuthStatus = "restoring" | "authenticated" | "unauthenticated";

interface AuthState {
  status: AuthStatus;
  user: UserResponse | null;
  sessionExpired: boolean;
  restoreSession: () => Promise<void>;
  login: (identifier: string, password: string) => Promise<void>;
  register: (params: { name: string; email: string; phone: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
  acknowledgeSessionExpired: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  status: "restoring",
  user: null,
  sessionExpired: false,

  restoreSession: async () => {
    const restored = await hydrateAuthTokens();
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
    await saveTokens({ accessToken: result.access_token, refreshToken: result.refresh_token });
    setAuthTokens({ accessToken: result.access_token, refreshToken: result.refresh_token });
    set({ status: "authenticated", user: result.user, sessionExpired: false });
  },

  register: async ({ name, email, phone, password }) => {
    const result = await authApi.register({ name, email, phone, password });
    await saveTokens({ accessToken: result.access_token, refreshToken: result.refresh_token });
    setAuthTokens({ accessToken: result.access_token, refreshToken: result.refresh_token });
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
