import { QueryClient } from "@tanstack/react-query";
import { toApiError } from "./errors";

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
    },
    mutations: {
      retry: false,
    },
  },
});
