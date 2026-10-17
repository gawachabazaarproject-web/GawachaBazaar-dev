import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

/** Value that follows `value` after it has stopped changing for `delayMs`
 * (keeps list pages from firing one API request per keystroke). */
export function useDebounced<T>(value: T, delayMs = 350): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/** Initial search text for a list page: the `?q=` of the URL (set by the
 * top-bar search) or empty. Safe on the server, where it returns "". */
export function readInitialQuery(): string {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("q") ?? "";
}

/** Keeps a list page's search box in step with `?q=` when the URL changes
 * while the page stays mounted (the top-bar search on the same list page).
 * Needs a <Suspense> ancestor - the admin layout provides one. */
export function useUrlQuerySync(onQuery: (q: string) => void): void {
  const urlQ = useSearchParams().get("q");
  const cb = useRef(onQuery);
  cb.current = onQuery;
  useEffect(() => {
    if (urlQ !== null) cb.current(urlQ);
  }, [urlQ]);
}
