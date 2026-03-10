import type { AccessSession, TokenPair } from "./types";

let accessSession: AccessSession | null = null;
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
    token_type: tokens.token_type
  };
  notifyListeners();
}

export function clearAccessSession(): void {
  accessSession = null;
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
