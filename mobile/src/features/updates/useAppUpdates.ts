import { useCallback, useState } from "react";
import * as Updates from "expo-updates";

/**
 * Over-the-air updates (EAS Update).
 *
 * Automatic: on every cold start expo-updates checks for a new JS bundle on
 * this build's channel and, if one is ready within `fallbackToCacheTimeout`
 * (see app.json), runs it straight away; otherwise it downloads in the
 * background and applies on the next cold start. Nothing here is needed for
 * that - this hook powers the manual "Check for updates" button.
 *
 * Updates are only available in EAS builds (preview/production). In Expo Go
 * and development builds `Updates.isEnabled` is false.
 */
export type UpdateStatus =
  | "idle"
  | "checking"
  | "downloading"
  | "up-to-date"
  | "ready" // downloaded; restart to run it
  | "unavailable" // not an EAS build (dev / Expo Go)
  | "error";

export interface AppUpdatesState {
  status: UpdateStatus;
  error: string | null;
  /** Check, and if a new version exists download it. Resolves true when one is ready to run. */
  check: () => Promise<boolean>;
  /** Restart the app into the downloaded update. */
  restart: () => Promise<void>;
}

/** Short id of the update currently running (null for the build's embedded bundle). */
export function runningUpdateLabel(): string | null {
  return Updates.isEnabled && Updates.updateId ? Updates.updateId.slice(0, 8) : null;
}

export function useAppUpdates(): AppUpdatesState {
  const [status, setStatus] = useState<UpdateStatus>(Updates.isEnabled ? "idle" : "unavailable");
  const [error, setError] = useState<string | null>(null);

  const check = useCallback(async (): Promise<boolean> => {
    if (!Updates.isEnabled) {
      setStatus("unavailable");
      return false;
    }
    setError(null);
    setStatus("checking");
    try {
      const result = await Updates.checkForUpdateAsync();
      if (!result.isAvailable) {
        setStatus("up-to-date");
        return false;
      }
      setStatus("downloading");
      await Updates.fetchUpdateAsync();
      setStatus("ready");
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't check for updates.");
      setStatus("error");
      return false;
    }
  }, []);

  const restart = useCallback(async () => {
    await Updates.reloadAsync();
  }, []);

  return { status, error, check, restart };
}
