/**
 * Indian mobile numbers <-> E.164 (+91XXXXXXXXXX), the format Firebase
 * Phone Auth requires. Mirrors backend normalize_phone for +91 numbers.
 */

/** Indian mobile numbers are 10 digits starting 6-9. */
const INDIAN_MOBILE = /^[6-9]\d{9}$/;

/** "98765 43210", "098765-43210", "+91 98765 43210", "919876543210"
 * -> "+919876543210"; anything else -> null. */
export function toIndianE164(input: string): string | null {
  let digits = input.replace(/\D/g, "");
  if (digits.length === 12 && digits.startsWith("91")) digits = digits.slice(2);
  else if (digits.length === 11 && digits.startsWith("0")) digits = digits.slice(1);
  return INDIAN_MOBILE.test(digits) ? `+91${digits}` : null;
}

/** "+919876543210" -> "+91 98765 43210" (display only). */
export function formatIndianPhone(e164: string): string {
  const m = /^\+91(\d{5})(\d{5})$/.exec(e164);
  return m ? `+91 ${m[1]} ${m[2]}` : e164;
}

/** Live formatting for the 10-digit input next to a fixed "+91" prefix. */
export function formatLocalDigits(input: string): string {
  const digits = input.replace(/\D/g, "").slice(0, 10);
  return digits.length > 5 ? `${digits.slice(0, 5)} ${digits.slice(5)}` : digits;
}

export function validateIndianMobile(input: string): string | null {
  if (!input.replace(/\D/g, "")) return "Enter your mobile number.";
  return toIndianE164(input) ? null : "Enter a valid 10-digit Indian mobile number.";
}
