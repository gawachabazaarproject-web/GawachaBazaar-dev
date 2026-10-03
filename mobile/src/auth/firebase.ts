/**
 * Firebase Auth - WEB implementation (Expo web build), on the firebase JS
 * SDK. Android/iOS resolve ./firebase.native.ts instead (Metro platform
 * extensions); both export exactly the same functions, typed here.
 *
 * Config: EXPO_PUBLIC_FIREBASE_* (public web config, not secrets). Each is
 * referenced literally so Expo inlines it at build time.
 */
import { FirebaseApp, getApps, initializeApp } from "firebase/app";
import {
  Auth,
  AuthCredential,
  ConfirmationResult,
  GoogleAuthProvider,
  RecaptchaVerifier,
  User,
  applyActionCode as fbApplyActionCode,
  browserLocalPersistence,
  confirmPasswordReset as fbConfirmPasswordReset,
  createUserWithEmailAndPassword,
  getAuth,
  getRedirectResult,
  linkWithCredential,
  linkWithPhoneNumber,
  onIdTokenChanged as fbOnIdTokenChanged,
  reload,
  sendEmailVerification,
  sendPasswordResetEmail,
  setPersistence,
  signInWithEmailAndPassword,
  signInWithPhoneNumber,
  signInWithPopup,
  signInWithRedirect,
  signOut as fbSignOut,
  updateProfile,
  verifyPasswordResetCode as fbVerifyPasswordResetCode,
} from "firebase/auth";
import { authErrorCode } from "./errors";
import { AccountExistsError, AuthUser, GoogleSignInResult, PhoneVerification } from "./types";

const config = {
  apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.EXPO_PUBLIC_FIREBASE_APP_ID,
};

export const firebaseConfigured = Object.values(config).every(Boolean);

let auth: Auth | null = null;
function fbAuth(): Auth {
  if (auth) return auth;
  if (!firebaseConfigured) throw Object.assign(new Error("Firebase is not configured"), { code: "auth/operation-not-allowed" });
  const app: FirebaseApp = getApps()[0] ?? initializeApp(config);
  auth = getAuth(app);
  void setPersistence(auth, browserLocalPersistence);
  return auth;
}

function toAuthUser(user: User | null): AuthUser | null {
  if (!user) return null;
  return {
    uid: user.uid,
    email: user.email,
    emailVerified: user.emailVerified,
    phoneNumber: user.phoneNumber,
    displayName: user.displayName,
    providerIds: user.providerData.map((p) => p.providerId),
  };
}

function requireUser(): User {
  const user = fbAuth().currentUser;
  if (!user) throw Object.assign(new Error("Not signed in"), { code: "auth/requires-recent-login" });
  return user;
}

// ---------------------------------------------------------------------------
// Session
// ---------------------------------------------------------------------------

export function onIdTokenChanged(listener: (user: AuthUser | null) => void): () => void {
  if (!firebaseConfigured) {
    listener(null);
    return () => undefined;
  }
  // Completes a signInWithRedirect fallback started before the page reload.
  getRedirectResult(fbAuth()).catch(() => undefined);
  return fbOnIdTokenChanged(fbAuth(), (user) => listener(toAuthUser(user)));
}

export function currentUser(): AuthUser | null {
  return firebaseConfigured ? toAuthUser(fbAuth().currentUser) : null;
}

/** Cached by the SDK; refreshed automatically when close to expiry. */
export async function getIdToken(forceRefresh = false): Promise<string | null> {
  const user = firebaseConfigured ? fbAuth().currentUser : null;
  return user ? user.getIdToken(forceRefresh) : null;
}

export async function reloadUser(): Promise<AuthUser | null> {
  const user = requireUser();
  await reload(user);
  await user.getIdToken(true); // new token carries the updated email_verified claim
  return toAuthUser(fbAuth().currentUser);
}

export async function signOut(): Promise<void> {
  pendingCredential = null;
  if (firebaseConfigured) await fbSignOut(fbAuth());
}

// ---------------------------------------------------------------------------
// Email + password
// ---------------------------------------------------------------------------

export async function signInWithEmail(email: string, password: string): Promise<void> {
  await signInWithEmailAndPassword(fbAuth(), email, password);
}

export async function registerWithEmail(email: string, password: string, displayName: string): Promise<void> {
  const { user } = await createUserWithEmailAndPassword(fbAuth(), email, password);
  await updateProfile(user, { displayName }).catch(() => undefined);
  await sendEmailVerification(user);
}

export async function sendVerificationEmail(): Promise<void> {
  await sendEmailVerification(requireUser());
}

export async function sendPasswordReset(email: string): Promise<void> {
  await sendPasswordResetEmail(fbAuth(), email);
}

/** For the in-app action handler (custom action URL). Returns the account email. */
export async function verifyPasswordResetCode(oobCode: string): Promise<string> {
  return fbVerifyPasswordResetCode(fbAuth(), oobCode);
}

export async function confirmPasswordReset(oobCode: string, newPassword: string): Promise<void> {
  await fbConfirmPasswordReset(fbAuth(), oobCode, newPassword);
}

export async function applyActionCode(oobCode: string): Promise<void> {
  await fbApplyActionCode(fbAuth(), oobCode);
}

// ---------------------------------------------------------------------------
// Google
// ---------------------------------------------------------------------------

let pendingCredential: AuthCredential | null = null;

export async function signInWithGoogle(): Promise<GoogleSignInResult> {
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });
  try {
    await signInWithPopup(fbAuth(), provider);
    return "success";
  } catch (err) {
    const code = authErrorCode(err);
    if (code === "auth/popup-closed-by-user" || code === "auth/cancelled-popup-request") return "cancelled";
    if (code === "auth/popup-blocked" || code === "auth/operation-not-supported-in-this-environment") {
      await signInWithRedirect(fbAuth(), provider); // page navigates away
      return "cancelled";
    }
    if (code === "auth/account-exists-with-different-credential") {
      pendingCredential = GoogleAuthProvider.credentialFromError(err as never);
      const email = (err as { customData?: { email?: string } }).customData?.email ?? null;
      throw new AccountExistsError(email);
    }
    throw err;
  }
}

/** After an AccountExistsError, once the customer signed in the original
 * way: attach the Google credential to that same Firebase user. */
export async function linkPendingCredential(): Promise<boolean> {
  if (!pendingCredential) return false;
  const credential = pendingCredential;
  pendingCredential = null;
  await linkWithCredential(requireUser(), credential);
  return true;
}

export function hasPendingCredential(): boolean {
  return pendingCredential !== null;
}

// ---------------------------------------------------------------------------
// Phone + OTP (web needs an invisible reCAPTCHA; native does not)
// ---------------------------------------------------------------------------

let verifier: RecaptchaVerifier | null = null;
function recaptcha(): RecaptchaVerifier {
  if (verifier) return verifier;
  let host = document.getElementById("recaptcha-container");
  if (!host) {
    host = document.createElement("div");
    host.id = "recaptcha-container";
    document.body.appendChild(host);
  }
  verifier = new RecaptchaVerifier(fbAuth(), host, { size: "invisible" });
  return verifier;
}

function resetRecaptcha(): void {
  verifier?.clear();
  verifier = null;
}

function wrap(result: ConfirmationResult, phoneNumber: string): PhoneVerification {
  return {
    phoneNumber,
    confirm: async (code: string) => {
      await result.confirm(code);
    },
  };
}

export async function startPhoneSignIn(phoneNumber: string): Promise<PhoneVerification> {
  try {
    return wrap(await signInWithPhoneNumber(fbAuth(), phoneNumber, recaptcha()), phoneNumber);
  } catch (err) {
    resetRecaptcha();
    throw err;
  }
}

/** Adds a verified phone number to the signed-in user (same Firebase UID). */
export async function startPhoneLink(phoneNumber: string): Promise<PhoneVerification> {
  try {
    return wrap(await linkWithPhoneNumber(requireUser(), phoneNumber, recaptcha()), phoneNumber);
  } catch (err) {
    resetRecaptcha();
    throw err;
  }
}
