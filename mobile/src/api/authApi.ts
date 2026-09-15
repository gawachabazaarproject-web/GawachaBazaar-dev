import { apiClient } from "./client";
import {
  LoginPayload,
  LoginResult,
  RefreshTokenResponse,
  RegisterPayload,
  TokenResponse,
  UserResponse,
} from "@/types/api";

export const authApi = {
  register: (payload: RegisterPayload) =>
    apiClient.post<TokenResponse>("/auth/register", payload).then((r) => r.data),

  login: (payload: LoginPayload) =>
    apiClient.post<LoginResult>("/auth/login", payload).then((r) => r.data),

  verifyLoginOtp: (challengeToken: string, code: string) =>
    apiClient
      .post<TokenResponse>("/auth/login/verify-otp", { challenge_token: challengeToken, code })
      .then((r) => r.data),

  refresh: (refreshToken: string) =>
    apiClient
      .post<RefreshTokenResponse>("/auth/refresh", { refresh_token: refreshToken })
      .then((r) => r.data),

  logout: (refreshToken: string) =>
    apiClient.post("/auth/logout", { refresh_token: refreshToken }).then((r) => r.data),

  me: () => apiClient.get<UserResponse>("/auth/me").then((r) => r.data),
};
