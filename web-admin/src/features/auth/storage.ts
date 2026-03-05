import type { TokenPair } from "./types";

const ACCESS_TOKEN_KEY = "go_admin_access_token";
const REFRESH_TOKEN_KEY = "go_admin_refresh_token";
const TOKEN_TYPE_KEY = "go_admin_token_type";

export function loadTokenPair(): TokenPair | null {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  const tokenType = localStorage.getItem(TOKEN_TYPE_KEY);
  if (!accessToken || !refreshToken || !tokenType) {
    return null;
  }
  return {
    access_token: accessToken,
    refresh_token: refreshToken,
    token_type: tokenType
  };
}

export function saveTokenPair(tokens: TokenPair): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  localStorage.setItem(TOKEN_TYPE_KEY, tokens.token_type);
}

export function clearTokenPair(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(TOKEN_TYPE_KEY);
}
