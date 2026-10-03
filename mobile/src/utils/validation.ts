/**
 * Lightweight client-side validation - purely for immediate UX feedback
 * (catching an obviously-empty or malformed field before a round trip).
 * The backend remains the sole authority on what's actually acceptable
 * (see RegisterRequest/LoginRequest in the API docs) - these checks are
 * intentionally a little looser than the backend's, so a real backend
 * rejection is still possible and still surfaced via ApiError.
 */

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateName(value: string): string | null {
  if (!value.trim()) return "Enter your full name.";
  if (value.trim().length < 2) return "Name must be at least 2 characters.";
  return null;
}

export function validateEmail(value: string): string | null {
  if (!value.trim()) return "Enter your email address.";
  if (!EMAIL_RE.test(value.trim())) return "Enter a valid email address.";
  return null;
}

export function validatePhone(value: string): string | null {
  const digits = value.replace(/\D/g, "");
  if (!digits) return "Enter your mobile number.";
  if (digits.length < 10) return "Enter a valid 10-digit mobile number.";
  return null;
}

export function validatePassword(value: string): string | null {
  if (!value) return "Enter a password.";
  if (value.length < 8) return "Password must be at least 8 characters.";
  return null;
}

export function validateRequired(value: string, label: string): string | null {
  if (!value.trim()) return `${label} is required.`;
  return null;
}

export function validateLoginIdentifier(value: string): string | null {
  if (!value.trim()) return "Enter your email or phone number.";
  if (value.trim().length < 3) return "Enter a valid email or phone number.";
  return null;
}

/** New-password rule for sign-up/reset. Keep in step with the Firebase
 * Console password policy (Authentication -> Settings -> Password policy)
 * so the server never rejects what this accepted. */
export function validateStrongPassword(value: string): string | null {
  if (!value) return "Enter a password.";
  if (value.length < 8) return "Use at least 8 characters.";
  if (value.length > 128) return "Use at most 128 characters.";
  if (!/[a-z]/.test(value)) return "Add a lowercase letter.";
  if (!/[A-Z]/.test(value)) return "Add an uppercase letter.";
  if (!/\d/.test(value)) return "Add a number.";
  return null;
}

export function validatePasswordConfirmation(password: string, confirmation: string): string | null {
  if (!confirmation) return "Re-enter your password.";
  return password === confirmation ? null : "Passwords don't match.";
}

export function validateNamePart(value: string, label: string): string | null {
  const v = value.trim();
  if (!v) return `Enter your ${label.toLowerCase()}.`;
  if (v.length > 75) return `${label} is too long.`;
  return null;
}
