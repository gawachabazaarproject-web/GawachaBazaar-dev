"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { ApiError, fetchMe, login as apiLogin, logout as apiLogout, refreshSession, UserProfile } from "./api";
import { canOpenAdminPanel } from "./permissions";

const REFRESH_TOKEN_KEY = "gawacha_admin.refresh_token";

interface AuthState {
  user: UserProfile | null;
  /** null = still resolving the initial session on page load. */
  status: "loading" | "authenticated" | "unauthenticated";
  error: string | null;
}

interface AuthContextValue extends AuthState {
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** For modules that need to call the API directly with a fresh token. */
  getAccessToken: () => string | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, status: "loading", error: null });
  const accessTokenRef = useRef<string | null>(null);

  const clearSession = useCallback(() => {
    accessTokenRef.current = null;
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setState({ user: null, status: "unauthenticated", error: null });
  }, []);

  const login = useCallback(async (identifier: string, password: string) => {
    setState((s) => ({ ...s, error: null }));
    try {
      const result = await apiLogin(identifier, password);
      if (!canOpenAdminPanel(result.user.roles)) {
        // Deliberately do not store any tokens for a user who cannot open
        // the admin panel at all - this is a real customer/wholesaler
        // account, not a staff account, and should never see this app.
        setState({
          user: null,
          status: "unauthenticated",
          error: "This account does not have access to the Gawacha Bazaar admin panel.",
        });
        return;
      }
      accessTokenRef.current = result.access_token;
      localStorage.setItem(REFRESH_TOKEN_KEY, result.refresh_token);
      setState({ user: result.user, status: "authenticated", error: null });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Unable to sign in. Please try again.";
      setState({ user: null, status: "unauthenticated", error: message });
    }
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (refreshToken) await apiLogout(refreshToken);
    clearSession();
  }, [clearSession]);

  const getAccessToken = useCallback(() => accessTokenRef.current, []);

  // On first load, silently re-establish the session from the stored
  // refresh token (survives a page reload without asking for a password
  // again) - mirrors the pattern already used by the mobile app.
  //
  // Guarded by a ref, not just the effect's own lifecycle: React Strict
  // Mode (on by default in Next dev) deliberately double-invokes effects,
  // and refresh-token rotation makes that fatal here - the second call
  // would present the OLD (now-invalidated-by-the-first-call) refresh
  // token, get rejected, and wipe out the session the first call just
  // legitimately established. This ref makes the refresh a true
  // once-per-mount action regardless of how many times the effect body
  // itself runs.
  const hasAttemptedRefresh = useRef(false);
  useEffect(() => {
    if (hasAttemptedRefresh.current) return;
    hasAttemptedRefresh.current = true;

    const storedRefreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (!storedRefreshToken) {
      setState({ user: null, status: "unauthenticated", error: null });
      return;
    }
    (async () => {
      try {
        const tokens = await refreshSession(storedRefreshToken);
        accessTokenRef.current = tokens.access_token;
        localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
        const profile = await fetchMe(tokens.access_token);
        if (!canOpenAdminPanel(profile.roles)) {
          clearSession();
          return;
        }
        setState({ user: profile, status: "authenticated", error: null });
      } catch {
        clearSession();
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, getAccessToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
