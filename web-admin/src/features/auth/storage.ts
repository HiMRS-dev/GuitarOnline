import type { AccessSession, TokenPair } from "./types";

const ACCESS_SESSION_STORAGE_KEY = "go_admin_access_session";

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function readAccessSession(): AccessSession | null {
  if (!canUseStorage()) {
    return null;
  }
  const raw = window.localStorage.getItem(ACCESS_SESSION_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as Partial<AccessSession>;
    if (
      typeof parsed.access_token !== "string" ||
      typeof parsed.refresh_token !== "string" ||
      typeof parsed.token_type !== "string"
    ) {
      window.localStorage.removeItem(ACCESS_SESSION_STORAGE_KEY);
      return null;
    }
    return {
      access_token: parsed.access_token,
      refresh_token: parsed.refresh_token,
      token_type: parsed.token_type
    };
  } catch {
    window.localStorage.removeItem(ACCESS_SESSION_STORAGE_KEY);
    return null;
  }
}

function persistAccessSession(session: AccessSession | null): void {
  if (!canUseStorage()) {
    return;
  }
  if (session === null) {
    window.localStorage.removeItem(ACCESS_SESSION_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(ACCESS_SESSION_STORAGE_KEY, JSON.stringify(session));
}

let accessSession: AccessSession | null = readAccessSession();
const listeners = new Set<(session: AccessSession | null) => void>();

function notifyListeners(): void {
  for (const listener of listeners) {
    listener(accessSession);
  }
}

export function loadAccessSession(): AccessSession | null {
  return accessSession;
}

export function saveTokenPair(tokens: TokenPair): void {
  accessSession = {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    token_type: tokens.token_type
  };
  persistAccessSession(accessSession);
  notifyListeners();
}

export function clearAccessSession(): void {
  accessSession = null;
  persistAccessSession(null);
  notifyListeners();
}

export function subscribeAccessSession(
  listener: (session: AccessSession | null) => void
): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
