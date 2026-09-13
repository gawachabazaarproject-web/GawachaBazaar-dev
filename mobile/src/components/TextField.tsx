import React, { forwardRef, useState } from "react";
import { Pressable, StyleSheet, TextInput, TextInputProps, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { Text } from "./Text";
import { colors, radius, spacing, typography } from "@/theme";

export interface TextFieldProps extends TextInputProps {
  label?: string;
  error?: string | null;
  helperText?: string;
}

export const TextField = forwardRef<TextInput, TextFieldProps>(
  ({ label, error, helperText, style, onFocus, onBlur, secureTextEntry, ...rest }, ref) => {
    const [focused, setFocused] = useState(false);
    // A field passed `secureTextEntry` gets a built-in show/hide toggle -
    // every password field in the app gets this for free, one place.
    const [revealed, setRevealed] = useState(false);
    const isPasswordField = secureTextEntry === true;

    return (
      <View style={styles.wrapper}>
        {label ? (
          <Text variant="bodyMedium" color={colors.textPrimary} style={styles.label}>
            {label}
          </Text>
        ) : null}
        <View style={styles.inputWrapper}>
          <TextInput
            ref={ref}
            style={[
              styles.input,
              focused && styles.inputFocused,
              !!error && styles.inputError,
              isPasswordField && styles.inputWithIcon,
              style,
            ]}
            placeholderTextColor={colors.textMuted}
            secureTextEntry={isPasswordField && !revealed}
            onFocus={(e) => {
              setFocused(true);
              onFocus?.(e);
            }}
            onBlur={(e) => {
              setFocused(false);
              onBlur?.(e);
            }}
            accessibilityLabel={label}
            {...rest}
          />
          {isPasswordField ? (
            <Pressable
              onPress={() => setRevealed((v) => !v)}
              style={styles.revealButton}
              hitSlop={10}
              accessibilityRole="button"
              accessibilityLabel={revealed ? "Hide password" : "Show password"}
            >
              <Feather name={revealed ? "eye-off" : "eye"} size={18} color={colors.textSecondary} />
            </Pressable>
          ) : null}
        </View>
        {error ? (
          <Text variant="caption" color={colors.error} style={styles.helper}>
            {error}
          </Text>
        ) : helperText ? (
          <Text variant="caption" color={colors.textMuted} style={styles.helper}>
            {helperText}
          </Text>
        ) : null}
      </View>
    );
  },
);
TextField.displayName = "TextField";

const styles = StyleSheet.create({
  wrapper: { width: "100%" },
  label: { marginBottom: spacing.xs },
  inputWrapper: { position: "relative", justifyContent: "center" },
  input: {
    ...typography.bodyLarge,
    color: colors.textPrimary,
    borderWidth: 1.5,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
  },
  inputWithIcon: { paddingRight: spacing["3xl"] },
  inputFocused: { borderColor: colors.primary },
  inputError: { borderColor: colors.error },
  revealButton: {
    position: "absolute",
    right: spacing.base,
    height: "100%",
    justifyContent: "center",
  },
  helper: { marginTop: spacing.xs },
});
