import React, { forwardRef, useState } from "react";
import { StyleSheet, TextInput, TextInputProps, View } from "react-native";
import { Text } from "./Text";
import { colors, radius, spacing, typography } from "@/theme";

export interface TextFieldProps extends TextInputProps {
  label?: string;
  error?: string | null;
  helperText?: string;
}

export const TextField = forwardRef<TextInput, TextFieldProps>(
  ({ label, error, helperText, style, onFocus, onBlur, ...rest }, ref) => {
    const [focused, setFocused] = useState(false);

    return (
      <View style={styles.wrapper}>
        {label ? (
          <Text variant="bodyMedium" color={colors.textPrimary} style={styles.label}>
            {label}
          </Text>
        ) : null}
        <TextInput
          ref={ref}
          style={[
            styles.input,
            focused && styles.inputFocused,
            !!error && styles.inputError,
            style,
          ]}
          placeholderTextColor={colors.textMuted}
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
  input: {
    ...typography.bodyLarge,
    color: colors.textPrimary,
    borderWidth: 1.5,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
  },
  inputFocused: { borderColor: colors.primary },
  inputError: { borderColor: colors.error },
  helper: { marginTop: spacing.xs },
});
