import { FormEvent, useMemo, useState } from "react";

import { API_BASE_URL } from "./config";
import { login } from "./features/auth/api";
import { clearTokenPair, loadTokenPair, saveTokenPair } from "./features/auth/storage";
import type { TokenPair } from "./features/auth/types";

function maskToken(token: string): string {
  if (token.length <= 12) {
    return token;
  }
  return `${token.slice(0, 8)}...${token.slice(-4)}`;
}

export function App() {
  const [tokens, setTokens] = useState<TokenPair | null>(() => loadTokenPair());
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isLoggedIn = useMemo(() => tokens !== null, [tokens]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const tokenPair = await login({ email, password });
      saveTokenPair(tokenPair);
      setTokens(tokenPair);
      setPassword("");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unexpected error");
    } finally {
      setPending(false);
    }
  }

  function handleLogout() {
    clearTokenPair();
    setTokens(null);
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">GuitarOnline</p>
        <h1>Admin Login Contract</h1>
        <p className="summary">
          This screen authenticates via <code>POST {API_BASE_URL}/identity/auth/login</code> and
          stores token pair in <code>localStorage</code> for v1.
        </p>
      </section>

      <section className="card">
        {!isLoggedIn ? (
          <form onSubmit={handleSubmit} className="auth-form">
            <label>
              <span>Email</span>
              <input
                type="email"
                name="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>

            <label>
              <span>Password</span>
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                required
                minLength={8}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>

            <button type="submit" disabled={pending}>
              {pending ? "Signing in..." : "Sign in"}
            </button>

            {error ? <p className="error-text">{error}</p> : null}
          </form>
        ) : (
          <div className="auth-state">
            <p className="success-text">Authenticated. Tokens are stored for current browser.</p>
            <p>
              <strong>access_token:</strong> <code>{maskToken(tokens.access_token)}</code>
            </p>
            <p>
              <strong>refresh_token:</strong> <code>{maskToken(tokens.refresh_token)}</code>
            </p>
            <p>
              <strong>token_type:</strong> <code>{tokens.token_type}</code>
            </p>
            <button type="button" onClick={handleLogout}>
              Sign out
            </button>
          </div>
        )}
      </section>
    </main>
  );
}
