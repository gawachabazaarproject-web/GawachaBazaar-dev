import React, { useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, TextInput, View } from "react-native";
import { Text } from "@/components/Text";
import { Button } from "@/components/Button";
import { useAuthStore, PhoneMode } from "@/store/authStore";
import { authErrorCode, authErrorMessage } from "@/auth/errors";
import { formatIndianPhone, formatLocalDigits, toIndianE164, validateIndianMobile } from "@/auth/phone";
import { colors, radius, spacing, typography } from "@/theme";
import { ErrorBanner, authStyles } from "./AuthParts";

/** Seconds left until `until` (epoch ms), ticking once a second. */
export function useCountdown(until: number): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (until <= Date.now()) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [until]);
  return Math.max(0, Math.ceil((until - now) / 1000));
}

/** Mobile number entry with a fixed +91 prefix. Sends ONE OTP per tap;
 * nothing is ever sent automatically. */
export function PhoneEntryStep({ mode, onSent }: { mode: PhoneMode; onSent: () => void }) {
  const loginWithPhone = useAuthStore((s) => s.loginWithPhone);
  const [digits, setDigits] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const send = async () => {
    setError(null);
    const invalid = validateIndianMobile(digits);
    setFieldError(invalid);
    if (invalid || sending) return;
    setSending(true);
    try {
      await loginWithPhone(toIndianE164(digits)!, mode);
      onSent();
    } catch (err) {
      setError(authErrorMessage(err, "Couldn't send the code. Please try again."));
    } finally {
      setSending(false);
    }
  };

  return (
    <View>
      <Text variant="bodyMedium" style={styles.label}>
        Mobile number
      </Text>
      <View style={[styles.phoneRow, fieldError ? styles.inputError : null]}>
        <Text variant="bodyLarge" style={styles.prefix}>
          +91
        </Text>
        <TextInput
          value={formatLocalDigits(digits)}
          onChangeText={(v) => {
            setDigits(v.replace(/\D/g, "").slice(0, 10));
            if (fieldError) setFieldError(null);
          }}
          onSubmitEditing={send}
          placeholder="98765 43210"
          placeholderTextColor={colors.textMuted}
          keyboardType="number-pad"
          textContentType="telephoneNumber"
          autoComplete="tel-national"
          maxLength={11}
          style={styles.phoneInput}
          accessibilityLabel="Mobile number"
        />
      </View>
      {fieldError ? (
        <Text variant="caption" color={colors.error} style={styles.helper}>
          {fieldError}
        </Text>
      ) : (
        <Text variant="caption" color={colors.textMuted} style={styles.helper}>
          We&apos;ll send a 6-digit code by SMS. Standard rates may apply.
        </Text>
      )}
      <ErrorBanner message={error} />
      <View style={authStyles.gapLg} />
      <Button label="Send code" onPress={send} loading={sending} fullWidth size="lg" />
    </View>
  );
}

const CODE_LENGTH = 6;

/** 6-digit OTP entry with a resend countdown. */
export function OtpStep({ onVerified, onChangeNumber }: { onVerified?: () => void; onChangeNumber: () => void }) {
  const verification = useAuthStore((s) => s.phoneVerification);
  const cooldownUntil = useAuthStore((s) => s.otpCooldownUntil);
  const verifyOTP = useAuthStore((s) => s.verifyOTP);
  const resendOTP = useAuthStore((s) => s.resendOTP);
  const secondsLeft = useCountdown(cooldownUntil);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [resending, setResending] = useState(false);
  const inputRef = useRef<TextInput>(null);

  const verify = async (value = code) => {
    if (value.length !== CODE_LENGTH || verifying) {
      if (value.length !== CODE_LENGTH) setError("Enter the 6-digit code.");
      return;
    }
    setError(null);
    setVerifying(true);
    try {
      await verifyOTP(value);
      onVerified?.();
    } catch (err) {
      const c = authErrorCode(err);
      if (c === "auth/code-expired" || c === "auth/session-expired" || c === "auth/invalid-verification-id") {
        setExpired(true);
      }
      setCode("");
      setError(authErrorMessage(err, "Couldn't verify the code. Please try again."));
      inputRef.current?.focus();
    } finally {
      setVerifying(false);
    }
  };

  const resend = async () => {
    setError(null);
    setResending(true);
    try {
      await resendOTP();
      setExpired(false);
      setCode("");
    } catch (err) {
      setError(authErrorMessage(err, "Couldn't send a new code. Please try again."));
    } finally {
      setResending(false);
    }
  };

  if (!verification) {
    return (
      <View>
        <ErrorBanner message="This code request has ended. Enter your number again." />
        <View style={authStyles.gapLg} />
        <Button label="Change number" onPress={onChangeNumber} fullWidth size="lg" />
      </View>
    );
  }

  return (
    <View>
      <Text variant="body" color={colors.textSecondary} align="center">
        Code sent to{" "}
        <Text variant="bodyMedium">{formatIndianPhone(verification.phoneNumber)}</Text>
      </Text>
      <Pressable onPress={() => inputRef.current?.focus()} style={styles.boxes} accessibilityLabel="Verification code">
        {Array.from({ length: CODE_LENGTH }).map((_, i) => {
          const active = i === code.length && !verifying;
          return (
            <View key={i} style={[styles.box, active && styles.boxActive, !!error && styles.boxError]}>
              <Text variant="h2">{code[i] ?? ""}</Text>
            </View>
          );
        })}
      </Pressable>
      {/* One real input behind the boxes: keeps paste + SMS autofill working. */}
      <TextInput
        ref={inputRef}
        value={code}
        onChangeText={(v) => {
          const next = v.replace(/\D/g, "").slice(0, CODE_LENGTH);
          setCode(next);
          if (error) setError(null);
          if (next.length === CODE_LENGTH) void verify(next);
        }}
        keyboardType="number-pad"
        textContentType="oneTimeCode"
        autoComplete="sms-otp"
        maxLength={CODE_LENGTH}
        autoFocus
        style={styles.hiddenInput}
        accessibilityLabel="Enter verification code"
      />
      <ErrorBanner message={error} />
      <View style={authStyles.gapLg} />
      <Button
        label={expired ? "Code expired" : "Verify"}
        onPress={() => verify()}
        loading={verifying}
        disabled={expired}
        fullWidth
        size="lg"
      />
      <View style={styles.resendRow}>
        {secondsLeft > 0 ? (
          <Text variant="bodySmall" color={colors.textMuted}>
            Resend code in {secondsLeft}s
          </Text>
        ) : (
          <Pressable onPress={resend} disabled={resending} accessibilityRole="button">
            <Text variant="bodyMedium" color={colors.primary}>
              {resending ? "Sending..." : "Resend code"}
            </Text>
          </Pressable>
        )}
        <Pressable onPress={onChangeNumber} accessibilityRole="button">
          <Text variant="bodyMedium" color={colors.primary}>
            Change number
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  label: { marginBottom: spacing.sm },
  phoneRow: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.borderStrong,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.base,
  },
  inputError: { borderColor: colors.error },
  prefix: { marginRight: spacing.sm, color: colors.textSecondary },
  phoneInput: { flex: 1, paddingVertical: spacing.md, ...typography.bodyLarge, color: colors.textPrimary },
  helper: { marginTop: spacing.xs },
  boxes: { flexDirection: "row", justifyContent: "space-between", marginTop: spacing.xl, gap: spacing.sm },
  box: {
    flex: 1,
    aspectRatio: 0.85,
    maxWidth: 56,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  boxActive: { borderColor: colors.primary, borderWidth: 2 },
  boxError: { borderColor: colors.error },
  hiddenInput: { position: "absolute", opacity: 0, height: 1, width: 1 },
  resendRow: { flexDirection: "row", justifyContent: "space-between", marginTop: spacing.lg },
});
