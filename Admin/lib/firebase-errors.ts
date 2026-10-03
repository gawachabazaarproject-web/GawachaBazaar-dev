/**
 * Firebase Auth error codes -> staff-facing messages. Raw Firebase
 * messages ("Firebase: Error (auth/...)") are never shown.
 */
const MESSAGES: Record<string, string> = {
  "auth/invalid-credential": "Incorrect email or password.",
  "auth/wrong-password": "Incorrect email or password.",
  "auth/user-not-found": "Incorrect email or password.",
  "auth/invalid-email": "Enter a valid email address.",
  "auth/missing-email": "Enter your email address.",
  "auth/missing-password": "Enter your password.",
  "auth/user-disabled": "This account has been disabled. Contact an administrator.",
  "auth/too-many-requests": "Too many attempts. Please wait a few minutes and try again.",
  "auth/network-request-failed": "Network error. Check your connection and try again.",
  "auth/expired-action-code": "This link has expired. Request a new one.",
  "auth/invalid-action-code": "This link is invalid or has already been used.",
};

export function firebaseErrorCode(err: unknown): string | null {
  if (err && typeof err === "object" && "code" in err && typeof (err as { code: unknown }).code === "string") {
    const code = (err as { code: string }).code;
    return code.startsWith("auth/") ? code : null;
  }
  return null;
}

export function firebaseErrorMessage(err: unknown, fallback = "Something went wrong. Please try again."): string {
  const code = firebaseErrorCode(err);
  return (code && MESSAGES[code]) || fallback;
}

/** Codes meaning "no such email/password user in Firebase" - the cue to try
 * the one-time legacy-account migration. */
export const NOT_IN_FIREBASE_CODES = new Set(["auth/invalid-credential", "auth/user-not-found", "auth/wrong-password"]);
