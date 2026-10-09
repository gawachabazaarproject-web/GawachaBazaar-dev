"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import {
  onIdTokenChanged,
  sendEmailVerification,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signOut,
  User as FirebaseUser,
} from "firebase/auth";
import { ApiError, fetchMe, migrateLegacyAccount, syncAccount, UserProfile } from "./api";
import { firebaseAuth, missingFirebaseConfig } from "./firebase";
import { firebaseErrorCode, firebaseErrorMessage, NOT_IN_FIREBASE_CODES } from "./firebase-errors";
import { canOpenAdminPanel } from "./permissions";

interface AuthState {
  user: UserProfile | null;
  /** "loading" while Firebase restores a persisted session on page load. */
  status: "loading" | "authenticated" | "unauthenticated";
  error: string | null;
}

interface AuthContextValue extends AuthState {
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Sends a Firebase password-reset email. Resolves even for unknown
   * addresses (no account enumeration). */
  forgotPassword: (email: string) => Promise<void>;
  /** Current Firebase ID token for API calls. Kept fresh by the SDK. */
  getAccessToken: () => string | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const NO_ACCESS = "This account does not have access to the Gawacha Bazaar admin panel.";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, status: "loading", error: null });
  const tokenRef = useRef<string | null>(null);
  const profileUidRef = useRef<string | null>(null);
  const verificationSentRef = useRef(false);

  const rejectSession = useCallback(async (error: string | null) => {
    tokenRef.current = null;
    profileUidRef.current = null;
    setState({ user: null, status: "unauthenticated", error });
    await signOut(firebaseAuth()).catch(() => undefined);
  }, []);

  // One listener drives the whole session: restores it on reload, reacts to
  // sign-in/sign-out, and receives every refreshed ID token (the SDK renews
  // it before its 1h expiry while a listener is attached), so
  // getAccessToken() never hands out a stale token.
  useEffect(() => {
    if (missingFirebaseConfig.length) {
      setState({ user: null, status: "unauthenticated", error: "Sign-in is not configured for this deployment." });
      return;
    }
    const auth = firebaseAuth();
    return onIdTokenChanged(auth, async (fbUser: FirebaseUser | null) => {
      if (!fbUser) {
        tokenRef.current = null;
        profileUidRef.current = null;
        setState((s) => ({ user: null, status: "unauthenticated", error: s.error }));
        return;
      }
      const token = await fbUser.getIdToken();
      tokenRef.current = token;
      if (profileUidRef.current === fbUser.uid) return; // token refresh only

      try {
        let profile: UserProfile;
        try {
          profile = await fetchMe(token);
        } catch (err) {
          if (!(err instanceof ApiError && err.code === "ACCOUNT_NOT_REGISTERED")) throw err;
          // Firebase knows this person but no staff record is linked yet.
          // The backend only links on a verified email, so prove it first.
          if (!fbUser.emailVerified && fbUser.providerData.some((p) => p.providerId === "password")) {
            await sendEmailVerification(fbUser).catch(() => undefined);
            await rejectSession(
              "Verify your email address first - we sent a link to your inbox. Then sign in again.",
            );
            return;
          }
          profile = await syncAccount(token);
        }
        if (!canOpenAdminPanel(profile.roles)) {
          await rejectSession(NO_ACCESS);
          return;
        }
        if (!profile.email_verified && profile.sign_in_provider === "password") {
          if (!verificationSentRef.current) {
            verificationSentRef.current = true;
            await sendEmailVerification(fbUser).catch(() => undefined);
          }
          await rejectSession(
            "Verify your email address first - we sent a link to your inbox. Then sign in again.",
          );
          return;
        }
        profileUidRef.current = fbUser.uid;
        setState({ user: profile, status: "authenticated", error: null });
      } catch (err) {
        const noAppUser = err instanceof ApiError && err.code === "ACCOUNT_NOT_REGISTERED";
        await rejectSession(
          noAppUser ? NO_ACCESS : err instanceof ApiError ? err.message : "Unable to sign in. Please try again.",
        );
      }
    });
  }, [rejectSession]);

  // The SDK's own refresh timer is throttled in background tabs and stops
  // across sleep, so the cached token can outlive its 1h life and the next
  // save fails with TOKEN_EXPIRED. Re-check whenever the tab comes back, the
  // network returns, and every few minutes; getIdToken() only hits the
  // network when the token is near expiry.
  useEffect(() => {
    if (missingFirebaseConfig.length) return;
    const auth = firebaseAuth();
    const refresh = () => {
      const fbUser = auth.currentUser;
      if (!fbUser) return;
      fbUser
        .getIdToken()
        .then((token) => {
          tokenRef.current = token;
        })
        .catch(() => undefined);
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") refresh();
    };
    const timer = window.setInterval(refresh, 5 * 60 * 1000);
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", refresh);
    window.addEventListener("online", refresh);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("online", refresh);
    };
  }, []);

  const login = useCallback(async (identifier: string, password: string) => {
    setState((s) => ({ ...s, error: null }));
    const auth = firebaseAuth();
    const trimmed = identifier.trim();
    const isEmail = trimmed.includes("@");

    try {
      if (isEmail) {
        try {
          await signInWithEmailAndPassword(auth, trimmed, password);
          return; // onIdTokenChanged takes it from here
        } catch (err) {
          if (!NOT_IN_FIREBASE_CODES.has(firebaseErrorCode(err) ?? "")) throw err;
        }
      }
      // Not a Firebase user (yet), or a phone number was entered: an account
      // from before the Firebase cutover moves over once, keeping its password.
      const { email } = await migrateLegacyAccount(trimmed, password);
      await signInWithEmailAndPassword(auth, email, password);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "PASSWORD_RESET_REQUIRED") {
          const email = (err.details as { email?: string } | null)?.email;
          if (email) await sendPasswordResetEmail(auth, email).catch(() => undefined);
          setState({ user: null, status: "unauthenticated", error: err.message });
          return;
        }
        const message = err.status === 401 ? "Incorrect email or password." : err.message;
        setState({ user: null, status: "unauthenticated", error: message });
        return;
      }
      setState({ user: null, status: "unauthenticated", error: firebaseErrorMessage(err, "Unable to sign in. Please try again.") });
    }
  }, []);

  const logout = useCallback(async () => {
    await rejectSession(null);
  }, [rejectSession]);

  const forgotPassword = useCallback(async (email: string) => {
    try {
      await sendPasswordResetEmail(firebaseAuth(), email.trim());
    } catch (err) {
      // Only surface actionable errors; "user not found" stays silent.
      const code = firebaseErrorCode(err);
      if (code === "auth/invalid-email" || code === "auth/too-many-requests" || code === "auth/network-request-failed") {
        throw new Error(firebaseErrorMessage(err));
      }
    }
  }, []);

  const getAccessToken = useCallback(() => tokenRef.current, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, forgotPassword, getAccessToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
