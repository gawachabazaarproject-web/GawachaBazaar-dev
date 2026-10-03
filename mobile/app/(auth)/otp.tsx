import React from "react";
import { useRouter } from "expo-router";
import { AuthScreen } from "@/features/auth/AuthParts";
import { OtpStep } from "@/features/auth/PhoneSteps";

export default function OtpScreen() {
  const router = useRouter();
  // On success the ID-token listener syncs the customer and AppGate
  // navigates on - nothing to do here.
  return (
    <AuthScreen title="Enter the code">
      <OtpStep onChangeNumber={() => router.replace("/(auth)/phone")} />
    </AuthScreen>
  );
}
