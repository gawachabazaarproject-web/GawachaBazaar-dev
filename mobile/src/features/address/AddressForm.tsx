import React, { useState } from "react";
import { Pressable, StyleSheet, Switch, View } from "react-native";
import { Text } from "@/components/Text";
import { TextField } from "@/components/TextField";
import { Button } from "@/components/Button";
import { colors, radius, spacing } from "@/theme";
import { AddressResponse, CreateAddressPayload } from "@/types/api";

const QUICK_LABELS = ["Home", "Work", "Other"];

export interface AddressFormValues {
  label: string;
  address_line_1: string;
  address_line_2: string;
  city: string;
  state: string;
  postal_code: string;
  is_default: boolean;
}

export interface AddressFormProps {
  initial?: AddressResponse;
  submitLabel: string;
  loading?: boolean;
  /** Hidden when this would be the user's only/first address - it's
   * forced default server-side regardless (see AddressService). */
  allowDefaultToggle?: boolean;
  onSubmit: (payload: CreateAddressPayload) => void;
}

export function AddressForm({ initial, submitLabel, loading, allowDefaultToggle = true, onSubmit }: AddressFormProps) {
  const [values, setValues] = useState<AddressFormValues>({
    label: initial?.label ?? "Home",
    address_line_1: initial?.address_line_1 ?? "",
    address_line_2: initial?.address_line_2 ?? "",
    city: initial?.city ?? "",
    state: initial?.state ?? "",
    postal_code: initial?.postal_code ?? "",
    is_default: initial?.is_default ?? false,
  });
  const [error, setError] = useState<string | null>(null);

  const set = <K extends keyof AddressFormValues>(key: K, value: AddressFormValues[K]) =>
    setValues((v) => ({ ...v, [key]: value }));

  const handleSubmit = () => {
    if (!values.label.trim() || !values.address_line_1.trim() || !values.city.trim() || !values.state.trim() || !values.postal_code.trim()) {
      setError("Please fill in all required fields.");
      return;
    }
    setError(null);
    onSubmit({
      label: values.label.trim(),
      address_line_1: values.address_line_1.trim(),
      address_line_2: values.address_line_2.trim() || null,
      city: values.city.trim(),
      state: values.state.trim(),
      postal_code: values.postal_code.trim(),
      is_default: values.is_default,
    });
  };

  return (
    <View>
      <Text variant="bodyMedium" style={styles.fieldLabel}>
        Label
      </Text>
      <View style={styles.chipRow}>
        {QUICK_LABELS.map((chip) => (
          <Pressable
            key={chip}
            onPress={() => set("label", chip)}
            style={[styles.chip, values.label === chip && styles.chipActive]}
          >
            <Text variant="bodySmall" color={values.label === chip ? colors.textInverse : colors.textPrimary}>
              {chip}
            </Text>
          </Pressable>
        ))}
      </View>
      {!QUICK_LABELS.includes(values.label) ? (
        <TextField value={values.label} onChangeText={(v) => set("label", v)} placeholder="Custom label" style={{ marginBottom: spacing.base }} />
      ) : null}

      <TextField
        label="Address line 1"
        placeholder="House / flat / street"
        value={values.address_line_1}
        onChangeText={(v) => set("address_line_1", v)}
      />
      <View style={{ height: spacing.base }} />
      <TextField
        label="Address line 2 (optional)"
        placeholder="Landmark, apartment, etc."
        value={values.address_line_2}
        onChangeText={(v) => set("address_line_2", v)}
      />
      <View style={{ height: spacing.base }} />
      <View style={styles.row}>
        <View style={styles.half}>
          <TextField label="City" value={values.city} onChangeText={(v) => set("city", v)} />
        </View>
        <View style={styles.half}>
          <TextField label="State" value={values.state} onChangeText={(v) => set("state", v)} />
        </View>
      </View>
      <View style={{ height: spacing.base }} />
      <TextField
        label="Postal code"
        keyboardType="number-pad"
        value={values.postal_code}
        onChangeText={(v) => set("postal_code", v)}
      />

      {allowDefaultToggle ? (
        <View style={styles.defaultRow}>
          <Text variant="bodyMedium">Set as default address</Text>
          <Switch
            value={values.is_default}
            onValueChange={(v) => set("is_default", v)}
            trackColor={{ true: colors.primary, false: colors.border }}
          />
        </View>
      ) : null}

      {error ? (
        <Text variant="bodySmall" color={colors.error} style={{ marginTop: spacing.md }}>
          {error}
        </Text>
      ) : null}

      <View style={{ height: spacing.xl }} />
      <Button label={submitLabel} onPress={handleSubmit} loading={loading} fullWidth size="lg" />
    </View>
  );
}

const styles = StyleSheet.create({
  fieldLabel: { marginBottom: spacing.sm },
  chipRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.base },
  chip: {
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: 1.5,
    borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  row: { flexDirection: "row", gap: spacing.base },
  half: { flex: 1 },
  defaultRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.lg,
    paddingVertical: spacing.sm,
  },
});
