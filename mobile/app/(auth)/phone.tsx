import React from "react";
import { Pressable, View } from "react-native";
import { useRouter } from "expo-router";
import { Text } from "@/components/Text";
import { colors } from "@/theme";
import { AuthScreen, authStyles } from "@/features/auth/AuthParts";
import { PhoneEntryStep } from "@/features/auth/PhoneSteps";

export default function PhoneScreen() {
  const router = useRouter();
  return (
    <AuthScreen title="Continue with phone" subtitle="New here or coming back - we'll send a one-time code to your mobile.">
      <PhoneEntryStep mode="signIn" onSent={() => router.push("/(auth)/otp")} />
      <View style={authStyles.footer}>
        <Pressable onPress={() => router.replace("/(auth)/login")} accessibilityRole="link" hitSlop={8}>
          <Text variant="bodyMedium" color={colors.primary}>
            Use email instead
          </Text>
        </Pressable>
      </View>
    </AuthScreen>
  );
}
