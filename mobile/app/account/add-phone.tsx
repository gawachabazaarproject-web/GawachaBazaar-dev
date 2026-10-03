import React, { useState } from "react";
import { Stack, useRouter } from "expo-router";
import { AuthScreen } from "@/features/auth/AuthParts";
import { OtpStep, PhoneEntryStep } from "@/features/auth/PhoneSteps";
import { useToastStore } from "@/store/toastStore";

/**
 * Adds a verified mobile number to the signed-in account (Firebase account
 * linking - same Firebase user, so still one Gawacha Bazaar customer).
 * Afterwards the customer can also sign in with phone + OTP.
 */
export default function AddPhoneScreen() {
  const router = useRouter();
  const [step, setStep] = useState<"phone" | "otp">("phone");

  return (
    <>
      <Stack.Screen options={{ headerShown: true, title: "Add mobile number" }} />
      {step === "phone" ? (
        <AuthScreen subtitle="We'll text a code to confirm this number is yours.">
          <PhoneEntryStep mode="link" onSent={() => setStep("otp")} />
        </AuthScreen>
      ) : (
        <AuthScreen title="Enter the code">
          <OtpStep
            onChangeNumber={() => setStep("phone")}
            onVerified={() => {
              useToastStore.getState().show("Mobile number added.", "success");
              router.back();
            }}
          />
        </AuthScreen>
      )}
    </>
  );
}
