/**
 * Firebase client for the admin panel. Firebase Auth holds staff
 * credentials; the backend verifies the resulting ID token on every
 * request and decides access from the roles stored in PostgreSQL.
 *
 * Config comes from NEXT_PUBLIC_FIREBASE_* (public by design - Firebase
 * web config is not a secret). Each variable is referenced literally so
 * Next.js can inline it at build time.
 */
import { FirebaseApp, getApps, initializeApp } from "firebase/app";
import { Auth, browserLocalPersistence, getAuth, setPersistence } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

/** Names of NEXT_PUBLIC_FIREBASE_* values that are not set (empty = ready). */
export const missingFirebaseConfig: string[] = Object.entries(firebaseConfig)
  .filter(([, value]) => !value)
  .map(([key]) => `NEXT_PUBLIC_FIREBASE_${key.replace(/[A-Z]/g, (c) => `_${c}`).toUpperCase()}`);

let auth: Auth | null = null;

/** Browser-only. Throws when the Firebase config is incomplete. */
export function firebaseAuth(): Auth {
  if (auth) return auth;
  if (missingFirebaseConfig.length) {
    throw new Error(`Firebase is not configured: missing ${missingFirebaseConfig.join(", ")}`);
  }
  const app: FirebaseApp = getApps()[0] ?? initializeApp(firebaseConfig);
  auth = getAuth(app);
  // Survive reloads; staff sign out explicitly on shared machines.
  void setPersistence(auth, browserLocalPersistence);
  return auth;
}
