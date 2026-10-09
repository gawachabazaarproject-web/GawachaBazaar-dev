import { useState } from "react";
import { Alert } from "react-native";
import {
  ExpoSpeechRecognitionModule,
  useSpeechRecognitionEvent,
} from "expo-speech-recognition";

/** Dictates into a search box: live partial text, final text on stop. */
export function useVoiceSearch(onText: (text: string) => void) {
  const [listening, setListening] = useState(false);

  useSpeechRecognitionEvent("start", () => setListening(true));
  useSpeechRecognitionEvent("end", () => setListening(false));
  useSpeechRecognitionEvent("result", (event) => {
    const text = event.results[0]?.transcript;
    if (text) onText(text);
  });
  useSpeechRecognitionEvent("error", (event) => {
    setListening(false);
    if (event.error !== "no-speech" && event.error !== "aborted") {
      Alert.alert("Voice search", "Couldn't hear you. Please try again.");
    }
  });

  const start = async () => {
    const perm = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("Microphone needed", "Allow microphone access in Settings to search by voice.");
      return;
    }
    ExpoSpeechRecognitionModule.start({ lang: "en-IN", interimResults: true });
  };

  const stop = () => ExpoSpeechRecognitionModule.stop();

  return { listening, toggle: () => (listening ? stop() : start()) };
}
