import { useCallback, useEffect, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";

const STORAGE_KEY = "gawachabazaar.recent_searches";
const MAX_RECENT = 8;

/** Local, non-sensitive presentation cache - deliberately AsyncStorage,
 * not secure-store (that's reserved for auth tokens only). */
export function useRecentSearches() {
  const [recent, setRecent] = useState<string[]>([]);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY).then((raw) => {
      if (raw) setRecent(JSON.parse(raw));
    });
  }, []);

  const addRecent = useCallback((term: string) => {
    setRecent((prev) => {
      const next = [term, ...prev.filter((t) => t.toLowerCase() !== term.toLowerCase())].slice(0, MAX_RECENT);
      AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next)).catch(() => undefined);
      return next;
    });
  }, []);

  const clearRecent = useCallback(() => {
    setRecent([]);
    AsyncStorage.removeItem(STORAGE_KEY).catch(() => undefined);
  }, []);

  return { recent, addRecent, clearRecent };
}
