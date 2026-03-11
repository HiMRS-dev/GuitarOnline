import { FormEvent, ReactNode, useEffect, useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

import { AdminLayout } from "./admin/AdminLayout";
import { AuditPage } from "./admin/pages/AuditPage";
import { CalendarPage } from "./admin/pages/CalendarPage";
import { KpiPage } from "./admin/pages/KpiPage";
import { PackagesPage } from "./admin/pages/PackagesPage";
import { StudentsPage } from "./admin/pages/StudentsPage";
import { TeachersPage } from "./admin/pages/TeachersPage";
import { UsersPage } from "./admin/pages/UsersPage";
import { getCurrentUser, login, logout } from "./features/auth/api";
import {
  clearAccessSession,
  loadAccessSession,
  saveTokenPair,
  subscribeAccessSession
} from "./features/auth/storage";
import type { AccessSession, TokenPair } from "./features/auth/types";

function maskToken(token: string): string {
  if (token.length <= 12) {
    return token;
  }
  return `${token.slice(0, 8)}...${token.slice(-4)}`;
}

export function App() {
  const [tokens, setTokens] = useState<AccessSession | null>(() => loadAccessSession());

  useEffect(() => {
    return subscribeAccessSession((session) => {
      setTokens(session);
    });
  }, []);

  function handleSignedIn(tokenPair: TokenPair) {
    saveTokenPair(tokenPair);
  }

  function handleSignOut() {
    void logout().catch(() => undefined);
    clearAccessSession();
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
            <AdminLayout onSignOut={handleSignOut} />
          </ProtectedAdminRoute>
        }
      >
        <Route index element={<Navigate to="kpi" replace />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="teachers" element={<TeachersPage />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="audit" element={<AuditPage />} />
        <Route path="students" element={<StudentsPage />} />
        <Route path="packages" element={<PackagesPage />} />
        <Route path="kpi" element={<KpiPage />} />
      </Route>
      <Route path="*" element={<Navigate to={tokens ? "/admin" : "/login"} replace />} />
    </Routes>
  );
}

type LoginPageProps = {
  tokens: AccessSession | null;
  onSignedIn: (tokenPair: TokenPair) => void;
  onSignOut: () => void;
};

function LoginPage({ tokens, onSignedIn, onSignOut }: LoginPageProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        {tokens === null ? (
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
  tokens: AccessSession | null;
  onInvalidSession: () => void;
  children: ReactNode;
};

function ProtectedAdminRoute({ tokens, onInvalidSession, children }: ProtectedAdminRouteProps) {
  const [state, setState] = useState<"pending" | "granted" | "denied">("pending");

  useEffect(() => {
    let active = true;
    setState("pending");
    getCurrentUser()
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
  }, [onInvalidSession, tokens?.access_token]);

  if (state === "denied") {
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
