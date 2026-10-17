import AsyncStorage from "@react-native-async-storage/async-storage";
import { ApiError } from "@/api/errors";

/**
 * Remembers the pay-first checkout session the shopper is paying for, so a
 * payment whose callback never reached the app (UPI hand-off lost, app killed,
 * network dropped) is re-checked with the backend on the next launch/resume.
 * Only the session id is stored - it is not a secret and grants nothing: the
 * backend still asks Razorpay and only acts for the signed-in owner.
 */
const KEY = "gb.pendingOnlineCheckout";
/** Matches the backend reconcile window - older sessions are no longer polled. */
const MAX_AGE_MS = 2 * 60 * 60 * 1000;

export async function rememberPendingCheckout(sessionId: number): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, JSON.stringify({ sessionId, at: Date.now() }));
  } catch {
    // Best effort: the webhook and the backend sweep still cover this payment.
  }
}

export async function forgetPendingCheckout(): Promise<void> {
  try {
    await AsyncStorage.removeItem(KEY);
  } catch {
    // ignore
  }
}

export async function readPendingCheckout(): Promise<number | null> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { sessionId?: number; at?: number };
    if (typeof parsed.sessionId !== "number" || typeof parsed.at !== "number") return null;
    if (Date.now() - parsed.at > MAX_AGE_MS) {
      await forgetPendingCheckout();
      return null;
    }
    return parsed.sessionId;
  } catch {
    return null;
  }
}

/**
 * True when a failed confirm/verify call says nothing about the payment itself
 * (offline, timeout, 5xx, expired sign-in, rate limit) - the money may well
 * have moved, so the customer must be told "confirming", never "failed".
 * False for a definite answer from the backend (e.g. 409: refunded).
 */
export function isUnknownOutcome(error: ApiError): boolean {
  const status = error.status;
  return error.isNetworkError || status === null || status >= 500 || status === 401 || status === 408 || status === 429;
}
