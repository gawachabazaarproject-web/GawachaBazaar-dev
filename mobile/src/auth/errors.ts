import { ApiError } from "@/api/errors";
import { AccountExistsError } from "./types";

/**
 * The single place Firebase Auth error codes become customer-facing text.
 * Raw Firebase/internal messages ("Firebase: Error (auth/...)") are never
 * shown. Both SDKs (native and web) use the same `auth/...` codes.
 */
const MESSAGES: Record<string, string> = {
  // Email / password
  "auth/invalid-credential": "Incorrect email or password.",
  "auth/wrong-password": "Incorrect email or password.",
  "auth/user-not-found": "Incorrect email or password.",
  "auth/invalid-login-credentials": "Incorrect email or password.",
  "auth/email-already-in-use": "An account with this email already exists. Try logging in instead.",
  "auth/weak-password": "Choose a stronger password.",
  "auth/password-does-not-meet-requirements": "Choose a stronger password.",
  "auth/invalid-email": "Enter a valid email address.",
  "auth/missing-email": "Enter your email address.",
  "auth/missing-password": "Enter your password.",
  "auth/user-disabled": "This account has been disabled. Please contact support.",
  "auth/requires-recent-login": "For your security, please log in again and retry.",
  // Links (verification / password reset)
  "auth/expired-action-code": "This link has expired. Request a new one.",
  "auth/invalid-action-code": "This link is invalid or has already been used.",
  // Google
  "auth/popup-closed-by-user": "Google sign-in was cancelled.",
  "auth/cancelled-popup-request": "Google sign-in was cancelled.",
  "auth/popup-blocked": "Your browser blocked the Google sign-in window. Allow pop-ups and try again.",
  "auth/account-exists-with-different-credential":
    "An account already exists with this email. Log in with your original method to link Google.",
  "auth/credential-already-in-use": "This sign-in method is already linked to another account.",
  "auth/provider-already-linked": "This sign-in method is already linked to your account.",
  "auth/operation-not-allowed": "This sign-in method isn't available right now.",
  "auth/unauthorized-domain": "Sign-in isn't available on this website address.",
  // Phone / OTP
  "auth/invalid-phone-number": "Enter a valid mobile number.",
  "auth/missing-phone-number": "Enter your mobile number.",
  "auth/invalid-verification-code": "That code is incorrect. Check the SMS and try again.",
  "auth/missing-verification-code": "Enter the 6-digit code.",
  "auth/code-expired": "This code has expired. Request a new one.",
  "auth/session-expired": "This code has expired. Request a new one.",
  "auth/invalid-verification-id": "This code has expired. Request a new one.",
  "auth/quota-exceeded": "We can't send more codes right now. Please try again later.",
  "auth/captcha-check-failed": "Verification failed. Please try again.",
  "auth/app-not-authorized": "This app isn't allowed to use phone sign-in yet.",
  "auth/missing-client-identifier": "This device couldn't be verified. Please try again.",
  // General
  "auth/too-many-requests": "Too many attempts. Please wait a few minutes and try again.",
  "auth/network-request-failed": "Network error. Check your connection and try again.",
  "auth/internal-error": "Something went wrong. Please try again.",
};

export function authErrorCode(err: unknown): string | null {
  if (err && typeof err === "object" && "code" in err) {
    const code = (err as { code: unknown }).code;
    if (typeof code === "string") {
      // RNFB sometimes prefixes the service ("auth/..."); web always does.
      return code.startsWith("auth/") ? code : `auth/${code}`;
    }
  }
  return null;
}

/** Customer-facing message for any error thrown by an auth action. */
export function authErrorMessage(err: unknown, fallback = "Something went wrong. Please try again."): string {
  if (err instanceof AccountExistsError) return MESSAGES["auth/account-exists-with-different-credential"];
  if (err instanceof ApiError) return err.message;
  const code = authErrorCode(err);
  if (code && MESSAGES[code]) return MESSAGES[code];
  return fallback;
}

/** "No such email/password user in Firebase" - the cue to try the
 * one-time migration of an account created before Firebase. */
export function isNotInFirebase(err: unknown): boolean {
  const code = authErrorCode(err);
  return (
    code === "auth/invalid-credential" ||
    code === "auth/user-not-found" ||
    code === "auth/wrong-password" ||
    code === "auth/invalid-login-credentials"
  );
}
