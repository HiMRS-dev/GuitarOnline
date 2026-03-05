import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

import { getCurrentUser, login } from "./features/auth/api";
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

  function handleSignedIn(tokenPair: TokenPair) {
    saveTokenPair(tokenPair);
    setTokens(tokenPair);
  }

  function handleSignOut() {
    clearTokenPair();
    setTokens(null);
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={
          <LoginPage tokens={tokens} onSignedIn={handleSignedIn} onSignOut={handleSignOut} />
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedAdminRoute tokens={tokens} onInvalidSession={handleSignOut}>
            <AdminHome onSignOut={handleSignOut} />
          </ProtectedAdminRoute>
        }
      />
      <Route path="*" element={<Navigate to={tokens ? "/admin" : "/login"} replace />} />
    </Routes>
  );
}

type LoginPageProps = {
  tokens: TokenPair | null;
  onSignedIn: (tokenPair: TokenPair) => void;
  onSignOut: () => void;
};

function LoginPage({ tokens, onSignedIn, onSignOut }: LoginPageProps) {
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
      onSignedIn(tokenPair);
      setPassword("");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unexpected error");
    } finally {
      setPending(false);
    }
  }

  function handleLogout() {
    onSignOut();
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">GuitarOnline</p>
        <h1>Admin Login Contract</h1>
        <p className="summary">
          Sign in to access protected admin routes. Missing or invalid session redirects here.
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
            <p className="success-text">Authenticated. Open the protected admin route.</p>
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
            <Link className="link-btn" to="/admin">
              Go to admin
            </Link>
          </div>
        )}
      </section>
    </main>
  );
}

type ProtectedAdminRouteProps = {
  tokens: TokenPair | null;
  onInvalidSession: () => void;
  children: ReactNode;
};

function ProtectedAdminRoute({ tokens, onInvalidSession, children }: ProtectedAdminRouteProps) {
  const [state, setState] = useState<"pending" | "granted" | "denied">("pending");

  useEffect(() => {
    if (!tokens) {
      setState("denied");
      return;
    }

    let active = true;
    setState("pending");
    getCurrentUser(tokens.access_token)
      .then((currentUser) => {
        if (!active) {
          return;
        }
        if (currentUser.role.name !== "admin") {
          onInvalidSession();
          setState("denied");
          return;
        }
        setState("granted");
      })
      .catch(() => {
        if (!active) {
          return;
        }
        onInvalidSession();
        setState("denied");
      });

    return () => {
      active = false;
    };
  }, [onInvalidSession, tokens]);

  if (!tokens || state === "denied") {
    return <Navigate to="/login" replace />;
  }
  if (state === "pending") {
    return (
      <main className="app-shell">
        <section className="card">
          <h2>Checking session...</h2>
          <p className="summary">Validating token and admin role gate.</p>
        </section>
      </main>
    );
  }

  return <>{children}</>;
}

type AdminHomeProps = {
  onSignOut: () => void;
};

function AdminHome({ onSignOut }: AdminHomeProps) {
  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">Admin Area</p>
        <h1>Protected Route Active</h1>
        <p className="summary">
          Session token exists and admin role check passed via <code>/identity/users/me</code>.
        </p>
      </section>
      <section className="card">
        <button type="button" onClick={onSignOut}>
          Sign out
        </button>
      </section>
    </main>
  );
}
