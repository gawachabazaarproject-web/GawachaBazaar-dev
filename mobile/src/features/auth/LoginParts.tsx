import React, { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  TextInputProps,
  View,
  useWindowDimensions,
} from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Feather, Ionicons } from "@expo/vector-icons";
import { Text } from "@/components/Text";
import { BazaarLoader } from "@/components/BazaarLoader";
import { SyncOverlay } from "./AuthParts";
import { colors, fontFamily } from "@/theme";

/**
 * Login screen built to the approved artwork (hero basket + logo on top,
 * cream card with rounded top corners, farm landscape at the bottom).
 * Every measurement below is the artwork's pixel value at its 819px width,
 * scaled to the device by `s`, so proportions match on any phone.
 */
const ART_WIDTH = 819;
const HERO_HEIGHT = 625; // hero crop height in artwork px
const CARD_TOP = 530; // where the card's top edge sits in the artwork
const FARM_HEIGHT = 297;

export function LoginShell({ children }: { children: React.ReactNode }) {
  const { width, height } = useWindowDimensions();
  const colWidth = Math.min(width, 560);
  const s = colWidth / ART_WIDTH;

  return (
    <View style={styles.root}>
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.select({ ios: "padding", android: undefined })}>
        <ScrollView
          style={styles.flex}
          contentContainerStyle={{ minHeight: height, alignItems: "center" }}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
          bounces={false}
        >
          <View style={{ width: colWidth, flexGrow: 1 }}>
            <Image
              source={require("../../../assets/login/hero.jpg")}
              style={{ width: colWidth, height: HERO_HEIGHT * s }}
              contentFit="cover"
              accessibilityLabel="Gawacha Bazaar - Fresh groceries, delivered fast"
            />
            <View
              style={{
                marginTop: -(HERO_HEIGHT - CARD_TOP) * s,
                backgroundColor: colors.authCard,
                borderTopLeftRadius: 80 * s,
                borderTopRightRadius: 80 * s,
                paddingTop: 90 * s,
                paddingHorizontal: 54 * s,
              }}
            >
              {children}
            </View>
            <View style={[styles.flex, { backgroundColor: colors.authCard, minHeight: 16 }]} />
            <View style={{ width: colWidth, height: FARM_HEIGHT * s }}>
              <Image
                source={require("../../../assets/login/farm.jpg")}
                style={StyleSheet.absoluteFill}
                contentFit="cover"
                accessible={false}
              />
              <LinearGradient
                pointerEvents="none"
                colors={[colors.authCard, "rgba(249,245,236,0)"]}
                style={{ position: "absolute", top: 0, left: 0, right: 0, height: 60 * s }}
              />
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
      <SyncOverlay />
    </View>
  );
}

/** Scale helper for the screen's own spacing. */
export function useLoginScale(): number {
  const { width } = useWindowDimensions();
  return Math.min(width, 560) / ART_WIDTH;
}

export function LoginGoogleButton({
  onPress,
  loading,
  disabled,
}: {
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
}) {
  const s = useLoginScale();
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      accessibilityRole="button"
      accessibilityLabel="Continue with Google"
      style={({ pressed }) => [
        styles.googleButton,
        { height: 122 * s, borderRadius: 40 * s, paddingHorizontal: 44 * s },
        (disabled || loading) && { opacity: 0.6 },
        pressed && { opacity: 0.85 },
      ]}
    >
      <Image
        source={require("../../../assets/login/google-g.png")}
        style={{ width: 58 * s, height: 58 * s }}
        contentFit="contain"
      />
      <View style={styles.googleLabel}>
        {loading ? (
          <BazaarLoader size={8} />
        ) : (
          <Text style={[styles.googleText, { fontSize: 37 * s }]}>Continue with Google</Text>
        )}
      </View>
      <Feather name="chevron-right" size={42 * s} color={colors.textPrimary} />
    </Pressable>
  );
}

export function LoginOrDivider() {
  const s = useLoginScale();
  return (
    <View style={[styles.divider, { marginVertical: 38 * s }]}>
      <View style={styles.line} />
      <Text variant="caption" color={colors.textMuted} style={styles.or}>
        OR
      </Text>
      <View style={styles.line} />
    </View>
  );
}

interface LoginFieldProps extends TextInputProps {
  label: string;
  icon: "mail" | "lock";
  error?: string | null;
}

export const LoginField = React.forwardRef<TextInput, LoginFieldProps>(
  ({ label, icon, error, secureTextEntry, ...rest }, ref) => {
    const s = useLoginScale();
    const [revealed, setRevealed] = useState(false);
    const [focused, setFocused] = useState(false);
    const isPassword = secureTextEntry === true;

    return (
      <View>
        <Text style={[styles.label, { fontSize: 35 * s, marginBottom: 18 * s }]}>{label}</Text>
        <View
          style={[
            styles.field,
            { height: 100 * s, borderRadius: 40 * s, paddingHorizontal: 22 * s },
            focused && { borderColor: colors.brandGreen },
            !!error && { borderColor: colors.error },
          ]}
        >
          <View style={[styles.iconCircle, { width: 62 * s, height: 62 * s, borderRadius: 31 * s }]}>
            <Feather name={icon} size={30 * s} color={colors.primary} />
          </View>
          <TextInput
            ref={ref}
            style={[styles.input, { fontSize: 33 * s, marginLeft: 36 * s }]}
            placeholderTextColor={colors.textMuted}
            secureTextEntry={isPassword && !revealed}
            autoCapitalize={isPassword ? "none" : undefined}
            autoCorrect={isPassword ? false : undefined}
            accessibilityLabel={label}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            {...rest}
          />
          {isPassword ? (
            <Pressable
              onPress={() => setRevealed((v) => !v)}
              hitSlop={12}
              accessibilityRole="button"
              accessibilityLabel={revealed ? "Hide password" : "Show password"}
              style={{ paddingHorizontal: 14 * s }}
            >
              <Feather name={revealed ? "eye-off" : "eye"} size={40 * s} color={colors.textPrimary} />
            </Pressable>
          ) : null}
        </View>
        {error ? (
          <Text variant="caption" color={colors.error} style={{ marginTop: 6 }}>
            {error}
          </Text>
        ) : null}
      </View>
    );
  },
);
LoginField.displayName = "LoginField";

export function LoginSubmitButton({
  label,
  onPress,
  loading,
  disabled,
}: {
  label: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
}) {
  const s = useLoginScale();
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [{ opacity: disabled ? 0.6 : pressed ? 0.9 : 1 }]}
    >
      <LinearGradient
        colors={[colors.authButtonStart, colors.authButtonEnd]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[styles.submit, { height: 111 * s, borderRadius: 40 * s }]}
      >
        <Ionicons
          name="leaf"
          size={120 * s}
          color="rgba(255,255,255,0.10)"
          style={[styles.submitLeaf, { right: 30 * s }]}
        />
        {loading ? (
          <BazaarLoader size={9} palette={[colors.white]} />
        ) : (
          <View style={styles.submitRow}>
            <Text style={[styles.submitText, { fontSize: 38 * s }]}>{label}</Text>
            <Feather name="arrow-right" size={44 * s} color={colors.white} style={{ marginLeft: 22 * s }} />
          </View>
        )}
      </LinearGradient>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  root: { flex: 1, backgroundColor: colors.authCard },
  googleButton: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.white,
    shadowColor: colors.primary,
    shadowOpacity: 0.1,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 6 },
    elevation: 4,
  },
  googleLabel: { flex: 1, alignItems: "center", justifyContent: "center", paddingRight: 8 },
  googleText: { fontFamily: fontFamily.bold, color: "#0E0E0E" },
  divider: { flexDirection: "row", alignItems: "center" },
  line: { flex: 1, height: StyleSheet.hairlineWidth * 2, backgroundColor: colors.borderStrong },
  or: { marginHorizontal: 22, letterSpacing: 1.5 },
  label: { fontFamily: fontFamily.bold, color: colors.textPrimary },
  field: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.white,
    borderWidth: 1.5,
    borderColor: colors.border,
  },
  iconCircle: { alignItems: "center", justifyContent: "center", backgroundColor: colors.authIconBg },
  input: { flex: 1, fontFamily: fontFamily.regular, color: colors.textPrimary, paddingVertical: 0 },
  submit: { alignItems: "center", justifyContent: "center", overflow: "hidden" },
  submitLeaf: { position: "absolute", bottom: -6 },
  submitRow: { flexDirection: "row", alignItems: "center" },
  submitText: { fontFamily: fontFamily.bold, color: colors.white },
});
