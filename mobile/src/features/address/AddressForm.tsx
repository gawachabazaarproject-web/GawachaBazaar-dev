import React, { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Switch, View } from "react-native";
import * as Location from "expo-location";
import { Feather } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { TextField } from "@/components/TextField";
import { Button } from "@/components/Button";
import { colors, radius, spacing } from "@/theme";
import { AddressResponse, CreateAddressPayload } from "@/types/api";
import { validateRequired } from "@/utils/validation";

const QUICK_LABELS = ["Home", "Work", "Other"];

/** Device GPS returns full float precision (e.g. 21.14663341962727),
 * which overflows the backend's `Decimal(max_digits=9, decimal_places=6)`
 * column and gets rejected with a 422. Round to 6 decimal places (~11cm
 * precision - far more than needed for delivery) before it ever leaves
 * the device. */
function roundCoord(value: number): number {
  return Math.round(value * 1e6) / 1e6;
}

export interface AddressFormValues {
  label: string;
  address_line_1: string;
  address_line_2: string;
  city: string;
  state: string;
  postal_code: string;
  is_default: boolean;
}

type FieldErrors = Partial<Record<"label" | "address_line_1" | "city" | "state" | "postal_code", string>>;

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
  const [coords, setCoords] = useState<{ latitude: number; longitude: number } | null>(
    initial?.latitude && initial?.longitude
      ? { latitude: Number.parseFloat(initial.latitude), longitude: Number.parseFloat(initial.longitude) }
      : null,
  );
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);

  const set = <K extends keyof AddressFormValues>(key: K, value: AddressFormValues[K]) => {
    setValues((v) => ({ ...v, [key]: value }));
    if (key in fieldErrors) setFieldErrors((e) => ({ ...e, [key]: undefined }));
  };

  const handleUseCurrentLocation = async () => {
    setError(null);
    setLocating(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") {
        setError("Location permission was denied. You can still enter your address manually.");
        return;
      }
      const position = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      const latitude = roundCoord(position.coords.latitude);
      const longitude = roundCoord(position.coords.longitude);
      setCoords({ latitude, longitude });

      const [place] = await Location.reverseGeocodeAsync({ latitude, longitude });
      if (place) {
        setValues((v) => ({
          ...v,
          address_line_1: [place.streetNumber, place.street].filter(Boolean).join(" ") || v.address_line_1,
          city: place.city ?? v.city,
          state: place.region ?? v.state,
          postal_code: place.postalCode ?? v.postal_code,
        }));
        setFieldErrors({});
      }
    } catch {
      setError("Couldn't detect your location. Please enter your address manually.");
    } finally {
      setLocating(false);
    }
  };

  const validate = (): FieldErrors => ({
    label: validateRequired(values.label, "Label") ?? undefined,
    address_line_1: validateRequired(values.address_line_1, "Address line 1") ?? undefined,
    city: validateRequired(values.city, "City") ?? undefined,
    state: validateRequired(values.state, "State") ?? undefined,
    postal_code: validateRequired(values.postal_code, "Postal code") ?? undefined,
  });

  const handleSubmit = () => {
    const errors = validate();
    setFieldErrors(errors);
    if (Object.values(errors).some(Boolean)) {
      setError(null);
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
      latitude: coords ? roundCoord(coords.latitude) : null,
      longitude: coords ? roundCoord(coords.longitude) : null,
      is_default: values.is_default,
    });
  };

  return (
    <View>
      <Pressable style={styles.locationButton} onPress={handleUseCurrentLocation} disabled={locating}>
        {locating ? (
          <ActivityIndicator size="small" color={colors.primary} />
        ) : (
          <Feather name="map-pin" size={16} color={colors.primary} />
        )}
        <Text variant="bodyMedium" color={colors.primary} style={{ marginLeft: spacing.sm }}>
          {locating ? "Detecting your location..." : "Use current location"}
        </Text>
      </Pressable>
      {coords ? (
        <Text variant="caption" color={colors.textMuted} style={styles.locationHint}>
          Location detected. You can still edit any field below.
        </Text>
      ) : null}

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
        <TextField
          value={values.label}
          onChangeText={(v) => set("label", v)}
          placeholder="Custom label"
          error={fieldErrors.label}
          style={{ marginBottom: spacing.base }}
        />
      ) : null}

      <TextField
        label="Address line 1"
        placeholder="House / flat / street"
        value={values.address_line_1}
        onChangeText={(v) => set("address_line_1", v)}
        error={fieldErrors.address_line_1}
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
          <TextField label="City" value={values.city} onChangeText={(v) => set("city", v)} error={fieldErrors.city} />
        </View>
        <View style={styles.half}>
          <TextField label="State" value={values.state} onChangeText={(v) => set("state", v)} error={fieldErrors.state} />
        </View>
      </View>
      <View style={{ height: spacing.base }} />
      <TextField
        label="Postal code"
        keyboardType="number-pad"
        value={values.postal_code}
        onChangeText={(v) => set("postal_code", v)}
        error={fieldErrors.postal_code}
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
  locationButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1.5,
    borderColor: colors.primary,
    borderRadius: radius.none,
    paddingVertical: spacing.md,
    marginBottom: spacing.sm,
  },
  locationHint: { textAlign: "center", marginBottom: spacing.base },
  fieldLabel: { marginBottom: spacing.sm },
  chipRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.base },
  chip: {
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    borderRadius: radius.none,
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
