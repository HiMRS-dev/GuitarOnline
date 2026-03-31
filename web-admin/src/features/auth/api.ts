import { apiClient } from "../../shared/api/client";
import { loadAccessSession } from "./storage";

import type { CurrentUser, LoginPayload, TokenPair } from "./types";

const CURRENT_USER_CACHE_TTL_MS = 15_000;

let cachedCurrentUser: CurrentUser | null = null;
let cachedCurrentUserExpiresAt = 0;
let cachedCurrentUserPromise: Promise<CurrentUser> | null = null;

export function invalidateCurrentUserCache(): void {
  cachedCurrentUser = null;
  cachedCurrentUserExpiresAt = 0;
  cachedCurrentUserPromise = null;
}

export async function login(payload: LoginPayload): Promise<TokenPair> {
  const tokenPair = await apiClient.request<TokenPair>("/identity/auth/login", {
    method: "POST",
    body: payload,
    auth: false
  });
  invalidateCurrentUserCache();
  return tokenPair;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  const now = Date.now();

  if (cachedCurrentUser !== null && cachedCurrentUserExpiresAt > now) {
    return cachedCurrentUser;
  }
  if (cachedCurrentUserPromise !== null && cachedCurrentUserExpiresAt > now) {
    return cachedCurrentUserPromise;
  }

  cachedCurrentUserPromise = apiClient
    .request<CurrentUser>("/identity/users/me")
    .then((currentUser) => {
      cachedCurrentUser = currentUser;
      cachedCurrentUserExpiresAt = Date.now() + CURRENT_USER_CACHE_TTL_MS;
      cachedCurrentUserPromise = null;
      return currentUser;
    })
    .catch((error) => {
      cachedCurrentUserPromise = null;
      cachedCurrentUserExpiresAt = 0;
      throw error;
    });

  cachedCurrentUserExpiresAt = now + CURRENT_USER_CACHE_TTL_MS;
  return cachedCurrentUserPromise;
}

export async function logout(): Promise<void> {
  invalidateCurrentUserCache();
  const session = loadAccessSession();
  await apiClient.request<void>("/identity/auth/logout", {
    method: "POST",
    body:
      session?.refresh_token && session.refresh_token.trim()
        ? { refresh_token: session.refresh_token }
        : undefined,
    auth: false,
    retryOnUnauthorized: false
  });
}
