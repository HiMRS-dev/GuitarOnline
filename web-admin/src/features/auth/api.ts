import { apiClient } from "../../shared/api/client";

import type { CurrentUser, LoginPayload, TokenPair } from "./types";

export async function login(payload: LoginPayload): Promise<TokenPair> {
  return apiClient.request<TokenPair>("/identity/auth/login", {
    method: "POST",
    body: payload,
    auth: false
  });
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return apiClient.request<CurrentUser>("/identity/users/me");
}
