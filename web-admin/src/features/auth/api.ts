import { API_BASE_URL } from "../../config";

import type { CurrentUser, LoginPayload, TokenPair } from "./types";

export async function login(payload: LoginPayload): Promise<TokenPair> {
  const response = await fetch(`${API_BASE_URL}/identity/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(errorBody?.detail || "Login failed");
  }

  return (await response.json()) as TokenPair;
}

export async function getCurrentUser(accessToken: string): Promise<CurrentUser> {
  const response = await fetch(`${API_BASE_URL}/identity/users/me`, {
    headers: {
      Authorization: `Bearer ${accessToken}`
    }
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(errorBody?.detail || "Session validation failed");
  }

  return (await response.json()) as CurrentUser;
}
