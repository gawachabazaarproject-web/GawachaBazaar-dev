/**
 * Firebase Auth - NATIVE implementation (Android/iOS), on
 * @react-native-firebase. Same exports as ./firebase.ts (web), which is
 * the file TypeScript checks callers against.
 *
 * Native config comes from google-services.json / GoogleService-Info.plist
 * baked into the build (see app.config.js). Google Sign-In additionally
 * needs EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID (the *Web* OAuth client id from
 * Firebase Console -> Authentication -> Google provider).
 *
 * Phone auth on native needs no reCAPTCHA: Firebase verifies the app with
 * Play Integrity (Android) / APNs (iOS) and may auto-read the SMS.
 */
import { getApps } from "@react-native-firebase/app";
import {
  GoogleAuthProvider,
  PhoneAuthProvider,
  applyActionCode as fbApplyActionCode,
  confirmPasswordReset as fbConfirmPasswordReset,
  createUserWithEmailAndPassword,
  getAuth,
  linkWithCredential,
  onIdTokenChanged as fbOnIdTokenChanged,
  reload,
  sendEmailVerification,
  sendPasswordResetEmail,
  signInWithCredential,
  signInWithEmailAndPassword,
  signInWithPhoneNumber,
  signOut as fbSignOut,
  updateProfile,
  verifyPasswordResetCode as fbVerifyPasswordResetCode,
  verifyPhoneNumber,
} from "@react-native-firebase/auth";
import type { AuthCredential, User } from "@react-native-firebase/auth";
import { GoogleSignin, isErrorWithCode, statusCodes } from "@react-native-google-signin/google-signin";
import { authErrorCode } from "./errors";
import { AccountExistsError, AuthUser, GoogleSignInResult, PhoneVerification } from "./types";

export const firebaseConfigured = getApps().length > 0;

const auth = () => getAuth();

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
  const user = auth().currentUser;
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
  return fbOnIdTokenChanged(auth(), (user) => listener(toAuthUser(user as User | null)));
}

export function currentUser(): AuthUser | null {
  return firebaseConfigured ? toAuthUser(auth().currentUser) : null;
}

export async function getIdToken(forceRefresh = false): Promise<string | null> {
  const user = firebaseConfigured ? auth().currentUser : null;
  return user ? user.getIdToken(forceRefresh) : null;
}

export async function reloadUser(): Promise<AuthUser | null> {
  const user = requireUser();
  await reload(user);
  await user.getIdToken(true);
  return toAuthUser(auth().currentUser);
}

export async function signOut(): Promise<void> {
  pendingCredential = null;
  await GoogleSignin.signOut().catch(() => undefined); // next Google sign-in shows the account picker
  if (firebaseConfigured) await fbSignOut(auth());
}

// ---------------------------------------------------------------------------
// Email + password
// ---------------------------------------------------------------------------

export async function signInWithEmail(email: string, password: string): Promise<void> {
  await signInWithEmailAndPassword(auth(), email, password);
}

export async function registerWithEmail(email: string, password: string, displayName: string): Promise<void> {
  const { user } = await createUserWithEmailAndPassword(auth(), email, password);
  await updateProfile(user, { displayName }).catch(() => undefined);
  await sendEmailVerification(user);
}

export async function sendVerificationEmail(): Promise<void> {
  await sendEmailVerification(requireUser());
}

export async function sendPasswordReset(email: string): Promise<void> {
  await sendPasswordResetEmail(auth(), email);
}

export async function verifyPasswordResetCode(oobCode: string): Promise<string> {
  return fbVerifyPasswordResetCode(auth(), oobCode);
}

export async function confirmPasswordReset(oobCode: string, newPassword: string): Promise<void> {
  await fbConfirmPasswordReset(auth(), oobCode, newPassword);
}

export async function applyActionCode(oobCode: string): Promise<void> {
  await fbApplyActionCode(auth(), oobCode);
}

// ---------------------------------------------------------------------------
// Google
// ---------------------------------------------------------------------------

let googleConfigured = false;
let pendingCredential: AuthCredential | null = null;

export async function signInWithGoogle(): Promise<GoogleSignInResult> {
  if (!googleConfigured) {
    const webClientId = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;
    if (!webClientId) throw Object.assign(new Error("Google not configured"), { code: "auth/operation-not-allowed" });
    GoogleSignin.configure({ webClientId });
    googleConfigured = true;
  }
  let idToken: string | null;
  try {
    await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
    const response = await GoogleSignin.signIn();
    if (response.type === "cancelled") return "cancelled";
    idToken = response.data.idToken;
  } catch (err) {
    if (isErrorWithCode(err)) {
      if (err.code === statusCodes.SIGN_IN_CANCELLED || err.code === statusCodes.IN_PROGRESS) return "cancelled";
      if (err.code === statusCodes.PLAY_SERVICES_NOT_AVAILABLE) {
        throw Object.assign(new Error("Play services missing"), { code: "auth/operation-not-allowed" });
      }
    }
    throw Object.assign(new Error("Google sign-in failed"), { code: "auth/internal-error" });
  }
  if (!idToken) throw Object.assign(new Error("No Google id token"), { code: "auth/internal-error" });

  const credential = GoogleAuthProvider.credential(idToken);
  try {
    await signInWithCredential(auth(), credential);
    return "success";
  } catch (err) {
    if (authErrorCode(err) === "auth/account-exists-with-different-credential") {
      pendingCredential = credential;
      const email = (err as { email?: string; customData?: { email?: string } }).customData?.email ?? null;
      throw new AccountExistsError(email);
    }
    throw err;
  }
}

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
// Phone + OTP
// ---------------------------------------------------------------------------

export async function startPhoneSignIn(phoneNumber: string): Promise<PhoneVerification> {
  const confirmation = await signInWithPhoneNumber(auth(), phoneNumber);
  return {
    phoneNumber,
    confirm: async (code: string) => {
      await confirmation.confirm(code);
    },
  };
}

/** Adds a verified phone number to the signed-in user (same Firebase UID). */
export async function startPhoneLink(phoneNumber: string): Promise<PhoneVerification> {
  const snapshot = await verifyPhoneNumber(auth(), phoneNumber);
  return {
    phoneNumber,
    confirm: async (code: string) => {
      const credential = PhoneAuthProvider.credential(snapshot.verificationId, code);
      await linkWithCredential(requireUser(), credential);
    },
  };
}
