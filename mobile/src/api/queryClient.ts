import { AppState } from "react-native";
import { QueryClient, dehydrate, focusManager, hydrate } from "@tanstack/react-query";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { toApiError } from "./errors";

// React Native has no window focus events - tell react-query when the app
// returns to the foreground so stale screens refetch.
AppState.addEventListener("change", (s) => focusManager.setFocused(s === "active"));

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        const apiError = toApiError(error);
        // Retry transient network issues once; never retry a definitive
        // 4xx (auth/validation/not-found retries would just repeat the
        // same failure).
        if (apiError.isNetworkError) return failureCount < 1;
        return false;
      },
      staleTime: 30_000,
      // Keep results around so going back to a screen is instant.
      gcTime: 30 * 60_000,
    },
    mutations: {
      retry: false,
    },
  },
});

/**
 * Public catalog data (no per-user content) is persisted so the next app
 * launch paints Home instantly from the last session while a background
 * refetch brings it up to date, instead of showing skeletons while a
 * (possibly cold) backend wakes up.
 */
const CACHE_KEY = "gb.queryCache.v1";
const PERSISTED_ROOTS = new Set(["categories", "category", "products", "product", "ads", "home-slides", "offers"]);
/** Detail screens and search/listing pages pile up as people browse; keep only
 * the most recently fetched ones so the stored cache stays small and fast. */
const MAX_PERSISTED_PER_ROOT: Record<string, number> = { product: 60, category: 30, products: 30 };
const MAX_CACHE_AGE_MS = 24 * 60 * 60_000;

export async function restoreQueryCache(): Promise<void> {
  try {
    const raw = await AsyncStorage.getItem(CACHE_KEY);
    if (!raw) return;
    const { savedAt, state } = JSON.parse(raw) as { savedAt: number; state: Parameters<typeof hydrate>[1] };
    if (Date.now() - savedAt > MAX_CACHE_AGE_MS) return;
    hydrate(queryClient, state);
  } catch {
    // A corrupt/unavailable cache just means a normal cold start.
  }
}

function saveQueryCache(): void {
  try {
    const state = dehydrate(queryClient, {
      shouldDehydrateQuery: (q) => q.state.status === "success" && PERSISTED_ROOTS.has(String(q.queryKey[0])),
    });
    for (const [root, max] of Object.entries(MAX_PERSISTED_PER_ROOT)) {
      const mine = state.queries.filter((q) => q.queryKey[0] === root);
      if (mine.length <= max) continue;
      const drop = new Set(
        mine.sort((a, b) => b.state.dataUpdatedAt - a.state.dataUpdatedAt).slice(max).map((q) => q.queryHash),
      );
      state.queries = state.queries.filter((q) => !drop.has(q.queryHash));
    }
    void AsyncStorage.setItem(CACHE_KEY, JSON.stringify({ savedAt: Date.now(), state })).catch(() => undefined);
  } catch {
    // Best-effort only.
  }
}

let persistTimer: ReturnType<typeof setTimeout> | null = null;
queryClient.getQueryCache().subscribe(() => {
  if (persistTimer) return;
  persistTimer = setTimeout(() => {
    persistTimer = null;
    saveQueryCache();
  }, 2000);
});

// The 2s debounce can lose the last updates when the OS kills a backgrounded app.
AppState.addEventListener("change", (s) => {
  if (s !== "active") saveQueryCache();
});
