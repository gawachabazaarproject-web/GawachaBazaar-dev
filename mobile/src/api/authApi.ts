import { apiClient } from "./client";
import {
  LoginPayload,
  RefreshTokenResponse,
  RegisterPayload,
  TokenResponse,
  UserResponse,
} from "@/types/api";

export const authApi = {
  register: (payload: RegisterPayload) =>
    apiClient.post<TokenResponse>("/auth/register", payload).then((r) => r.data),

  login: (payload: LoginPayload) =>
    apiClient.post<TokenResponse>("/auth/login", payload).then((r) => r.data),

  refresh: (refreshToken: string) =>
    apiClient
      .post<RefreshTokenResponse>("/auth/refresh", { refresh_token: refreshToken })
      .then((r) => r.data),

  logout: (refreshToken: string) =>
    apiClient.post("/auth/logout", { refresh_token: refreshToken }).then((r) => r.data),

  me: () => apiClient.get<UserResponse>("/auth/me").then((r) => r.data),
};
