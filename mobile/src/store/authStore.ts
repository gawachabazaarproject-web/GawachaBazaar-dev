import { create } from "zustand";
import { authApi, setAuthFailureHandler, toApiError, ApiError } from "@/api";
import { queryClient } from "@/api/queryClient";
import * as fb from "@/auth/firebase";
import { authErrorCode, authErrorMessage, isNotInFirebase } from "@/auth/errors";
import { AccountExistsError, AuthUser, GoogleSignInResult, PhoneVerification } from "@/auth/types";
import { AuthUserResponse } from "@/types/api";

/**
 * The one place authentication state lives. Screens call these actions and
 * read this state - none of them talk to Firebase or /auth/* directly.
 *
 * Flow: Firebase signs the customer in (email/password, Google, or phone
 * OTP) -> the Firebase ID-token listener fires -> POST /auth/sync maps the
 * verified identity to the Gawacha Bazaar customer -> status settles.
 *
 * status:
 * - restoring       Firebase is restoring a persisted session (splash)
 * - unauthenticated no Firebase user (or the backend refused it)
 * - verifyingEmail  email/password account whose email isn't verified yet
 * - authenticated   ready; every protected route works
 */
export type AuthStatus = "restoring" | "unauthenticated" | "verifyingEmail" | "authenticated";

export type PhoneMode = "signIn" | "link";

/** OTP sending is billable: at most one send per RESEND_COOLDOWN_MS per
 * number, and MAX_SENDS per number per SEND_WINDOW_MS. Firebase enforces
 * its own server-side limits on top of this. */
export const RESEND_COOLDOWN_MS = 60_000;
const MAX_SENDS = 3;
const SEND_WINDOW_MS = 15 * 60_000;
export const VERIFICATION_EMAIL_COOLDOWN_MS = 60_000;
const SURFACED_RESET_ERRORS = new Set([
  "auth/invalid-email",
  "auth/missing-email",
  "auth/too-many-requests",
  "auth/network-request-failed",
]);

interface AuthState {
  status: AuthStatus;
  /** Gawacha Bazaar customer (PostgreSQL), incl. email_verified. */
  user: AuthUserResponse | null;
  firebaseUser: AuthUser | null;
  loading: boolean;
  isAuthenticated: boolean;
  isEmailVerified: boolean;
  /** Session-level problem to show on the login screen (e.g. the account
   * exists under another sign-in method, or was disabled). */
  authError: string | null;
  /** Email the customer should use to finish linking a Google sign-in. */
  linkEmail: string | null;
  phoneVerification: PhoneVerification | null;
  phoneMode: PhoneMode;
  otpCooldownUntil: number;
  verificationEmailCooldownUntil: number;

  restoreSession: () => void;
  login: (email: string, password: string) => Promise<void>;
  register: (p: { firstName: string; lastName: string; email: string; password: string }) => Promise<void>;
  loginWithGoogle: () => Promise<GoogleSignInResult>;
  /** Sends the OTP. `phoneE164` like +919876543210. */
  loginWithPhone: (phoneE164: string, mode?: PhoneMode) => Promise<void>;
  resendOTP: () => Promise<void>;
  verifyOTP: (code: string) => Promise<void>;
  logout: () => Promise<void>;
  forgotPassword: (email: string) => Promise<void>;
  resendVerificationEmail: () => Promise<void>;
  /** Re-reads the Firebase user + backend profile (e.g. after the customer
   * clicked the verification link). Returns true once the email is verified. */
  refreshUser: () => Promise<boolean>;
  clearAuthError: () => void;
}

function needsEmailVerification(user: AuthUserResponse): boolean {
  return user.sign_in_provider === "password" && !!user.email && !user.email_verified;
}

function derived(status: AuthStatus, user: AuthUserResponse | null) {
  return {
    status,
    user,
    loading: status === "restoring",
    isAuthenticated: status === "authenticated",
    isEmailVerified: !!user?.email_verified,
  };
}

// Module state that must not trigger renders.
let unsubscribe: (() => void) | null = null;
let syncedUid: string | null = null;
let syncInFlight: Promise<void> | null = null;
/** Names typed on the register screen, sent with the first sync. */
let pendingProfile: { first_name?: string; last_name?: string } | null = null;
const otpSends = new Map<string, number[]>();

export const useAuthStore = create<AuthState>((set, get) => {
  /** Map the verified Firebase user to the backend customer. */
  const syncWithBackend = (fbUser: AuthUser): Promise<void> => {
    if (syncInFlight) return syncInFlight;
    syncInFlight = (async () => {
      try {
        const profile = pendingProfile ?? {};
        const user = await authApi.sync(profile);
        pendingProfile = null;
        syncedUid = fbUser.uid;
        set({
          ...derived(needsEmailVerification(user) ? "verifyingEmail" : "authenticated", user),
          authError: null,
        });
      } catch (err) {
        const apiErr = toApiError(err);
        syncedUid = null;
        if (apiErr.isNetworkError || apiErr.status === 503) {
          // Keep the Firebase session; the next app start or login retries.
          set({ ...derived("unauthenticated", null), authError: apiErr.message });
          return;
        }
        // Backend refused this identity (disabled, or the email/phone
        // belongs to an account using another sign-in method).
        await fb.signOut().catch(() => undefined);
        set({
          ...derived("unauthenticated", null),
          authError: apiErr.message,
          linkEmail: apiErr.code === "ACCOUNT_EXISTS_DIFFERENT_METHOD" ? fbUser.email : null,
        });
      } finally {
        syncInFlight = null;
      }
    })();
    return syncInFlight;
  };

  const handleFirebaseUser = async (fbUser: AuthUser | null) => {
    if (!fbUser) {
      syncedUid = null;
      // Every cached query belonged to the session that just ended.
      queryClient.clear();
      set((s) => ({ ...derived("unauthenticated", null), firebaseUser: null, authError: s.authError }));
      return;
    }
    set({ firebaseUser: fbUser });
    if (syncedUid === fbUser.uid && get().user) return; // hourly token refresh only
    await syncWithBackend(fbUser);
  };

  const sendOtp = async (phoneE164: string, mode: PhoneMode) => {
    const now = Date.now();
    const recent = (otpSends.get(phoneE164) ?? []).filter((t) => now - t < SEND_WINDOW_MS);
    const last = recent[recent.length - 1];
    if (last && now - last < RESEND_COOLDOWN_MS) {
      const wait = Math.ceil((RESEND_COOLDOWN_MS - (now - last)) / 1000);
      throw new ApiError({ message: `Please wait ${wait}s before requesting another code.`, code: "OTP_COOLDOWN", status: null });
    }
    if (recent.length >= MAX_SENDS) {
      throw new ApiError({
        message: "Too many codes requested for this number. Please try again in 15 minutes.",
        code: "OTP_LIMIT",
        status: null,
      });
    }
    const verification = mode === "link" ? await fb.startPhoneLink(phoneE164) : await fb.startPhoneSignIn(phoneE164);
    otpSends.set(phoneE164, [...recent, Date.now()]);
    set({ phoneVerification: verification, phoneMode: mode, otpCooldownUntil: Date.now() + RESEND_COOLDOWN_MS });
  };

  return {
    ...derived("restoring", null),
    firebaseUser: null,
    authError: null,
    linkEmail: null,
    phoneVerification: null,
    phoneMode: "signIn",
    otpCooldownUntil: 0,
    verificationEmailCooldownUntil: 0,

    restoreSession: () => {
      if (unsubscribe) return;
      unsubscribe = fb.onIdTokenChanged((user) => {
        void handleFirebaseUser(user);
      });
    },

    login: async (email, password) => {
      set({ authError: null });
      const trimmed = email.trim().toLowerCase();
      try {
        await fb.signInWithEmail(trimmed, password);
      } catch (err) {
        if (!isNotInFirebase(err)) throw err;
        // Maybe an account from before Firebase: move it over once,
        // keeping its password. Wrong credentials stay "incorrect".
        let migratedEmail: string;
        try {
          migratedEmail = (await authApi.legacyMigrate(trimmed, password)).email;
        } catch (migrationErr) {
          const apiErr = toApiError(migrationErr);
          if (apiErr.code === "PASSWORD_RESET_REQUIRED") {
            const resetEmail = (apiErr.details as { email?: string } | null)?.email ?? trimmed;
            await fb.sendPasswordReset(resetEmail).catch(() => undefined);
            throw apiErr;
          }
          if (apiErr.status === 401 || apiErr.status === 422) throw err; // "Incorrect email or password."
          throw apiErr;
        }
        await fb.signInWithEmail(migratedEmail, password);
      }
      // Finishing a Google-link started from AccountExistsError.
      if (fb.hasPendingCredential()) {
        await fb.linkPendingCredential().catch((e) => set({ authError: authErrorMessage(e) }));
        set({ linkEmail: null });
      }
    },

    register: async ({ firstName, lastName, email, password }) => {
      set({ authError: null });
      pendingProfile = { first_name: firstName.trim(), last_name: lastName.trim() };
      try {
        await fb.registerWithEmail(email.trim().toLowerCase(), password, `${firstName} ${lastName}`.trim());
        set({ verificationEmailCooldownUntil: Date.now() + VERIFICATION_EMAIL_COOLDOWN_MS });
      } catch (err) {
        pendingProfile = null;
        throw err;
      }
    },

    loginWithGoogle: async () => {
      set({ authError: null });
      try {
        return await fb.signInWithGoogle();
      } catch (err) {
        if (err instanceof AccountExistsError) set({ linkEmail: err.email });
        throw err;
      }
    },

    loginWithPhone: async (phoneE164, mode = "signIn") => {
      set({ authError: null });
      await sendOtp(phoneE164, mode);
    },

    resendOTP: async () => {
      const current = get().phoneVerification;
      if (!current) throw new ApiError({ message: "Enter your mobile number again.", code: "OTP_MISSING", status: null });
      await sendOtp(current.phoneNumber, get().phoneMode);
    },

    verifyOTP: async (code) => {
      const verification = get().phoneVerification;
      if (!verification) throw new ApiError({ message: "This code has expired. Request a new one.", code: "OTP_MISSING", status: null });
      await verification.confirm(code);
      set({ phoneVerification: null });
      if (get().phoneMode === "link") {
        // Same Firebase user, now with a phone: copy it to the customer.
        const user = await authApi.sync();
        set({ user });
      }
      // signIn mode: the ID-token listener syncs and settles status.
    },

    logout: async () => {
      pendingProfile = null;
      set({ phoneVerification: null, authError: null, linkEmail: null });
      await fb.signOut();
      // handleFirebaseUser(null) resets the rest.
    },

    forgotPassword: async (email) => {
      try {
        await fb.sendPasswordReset(email.trim().toLowerCase());
      } catch (err) {
        // Never reveal whether an account exists - only surface errors the
        // customer can act on.
        const code = authErrorCode(err);
        if (code && SURFACED_RESET_ERRORS.has(code)) throw err;
      }
    },

    resendVerificationEmail: async () => {
      const until = get().verificationEmailCooldownUntil;
      if (Date.now() < until) {
        throw new ApiError({
          message: `Please wait ${Math.ceil((until - Date.now()) / 1000)}s before sending another email.`,
          code: "VERIFY_COOLDOWN",
          status: null,
        });
      }
      await fb.sendVerificationEmail();
      set({ verificationEmailCooldownUntil: Date.now() + VERIFICATION_EMAIL_COOLDOWN_MS });
    },

    refreshUser: async () => {
      const fbUser = await fb.reloadUser();
      set({ firebaseUser: fbUser });
      const user = await authApi.me();
      set(derived(needsEmailVerification(user) ? "verifyingEmail" : "authenticated", user));
      return !!user.email_verified || user.sign_in_provider !== "password";
    },

    clearAuthError: () => set({ authError: null, linkEmail: null }),
  };
});

// Backend rejected a request from an otherwise signed-in session.
setAuthFailureHandler((code) => {
  const { status } = useAuthStore.getState();
  if (status === "unauthenticated" || status === "restoring") return;
  if (code === "EMAIL_NOT_VERIFIED") {
    useAuthStore.setState({ status: "verifyingEmail", isAuthenticated: false });
    return;
  }
  // Disabled account, unknown/removed customer, revoked session.
  void useAuthStore
    .getState()
    .logout()
    .then(() => useAuthStore.setState({ authError: "Your session has ended. Please log in again." }));
});
