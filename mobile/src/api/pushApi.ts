import { apiClient } from "./client";

export const pushApi = {
  register: (token: string, platform: string): Promise<void> =>
    apiClient.post("/push-tokens", { token, platform }).then(() => undefined),
  unregister: (token: string): Promise<void> =>
    apiClient.post("/push-tokens/unregister", { token }).then(() => undefined),
};
