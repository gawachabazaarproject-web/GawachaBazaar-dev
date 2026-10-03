import { apiClient } from "./client";
import { AuthUserResponse, LegacyMigrationResponse, SyncUserPayload } from "@/types/api";

export const authApi = {
  /** After every Firebase sign-in: find/link/create the app user for the
   * verified Firebase identity. Identity comes only from the token. */
  sync: (payload: SyncUserPayload = {}) =>
    apiClient.post<AuthUserResponse>("/auth/sync", payload).then((r) => r.data),

  me: () => apiClient.get<AuthUserResponse>("/auth/me").then((r) => r.data),

  /** One-time move of an account created before Firebase (see backend
   * AuthService.migrate_legacy_account). */
  legacyMigrate: (identifier: string, password: string) =>
    apiClient
      .post<LegacyMigrationResponse>("/auth/legacy-migrate", { identifier, password })
      .then((r) => r.data),
};
