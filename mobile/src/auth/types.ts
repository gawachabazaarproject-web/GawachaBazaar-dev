/** Platform-neutral view of the signed-in Firebase user. The native
 * (@react-native-firebase) and web (firebase JS SDK) implementations in
 * ./firebase.native.ts and ./firebase.ts both map their own User to this. */
export interface AuthUser {
  uid: string;
  email: string | null;
  emailVerified: boolean;
  phoneNumber: string | null;
  displayName: string | null;
  /** e.g. ["password"], ["google.com", "phone"] */
  providerIds: string[];
}

/** An OTP that has been sent and is waiting for the customer's code. */
export interface PhoneVerification {
  phoneNumber: string;
  confirm: (code: string) => Promise<void>;
}

export type GoogleSignInResult = "success" | "cancelled";

/** Thrown when the email already belongs to an account with a different
 * sign-in method. The attempted credential is kept (see
 * `linkPendingCredential`) so it can be attached after the customer signs
 * in the original way. */
export class AccountExistsError extends Error {
  readonly email: string | null;
  constructor(email: string | null) {
    super("An account already exists with this email.");
    this.email = email;
  }
}
