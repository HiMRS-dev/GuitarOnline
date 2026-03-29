import { FormEvent, ReactNode, Suspense, lazy, useCallback, useEffect, useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

import { AdminLayout } from "./admin/AdminLayout";
import { getCurrentUser, login, logout } from "./features/auth/api";
import { CurrentUserProvider } from "./features/auth/currentUser";
import {
  clearAccessSession,
  loadAccessSession,
  saveTokenPair,
  subscribeAccessSession
} from "./features/auth/storage";
import type { AccessSession, CurrentUser, TokenPair } from "./features/auth/types";

const AuditPage = lazy(() =>
  import("./admin/pages/AuditPage").then((module) => ({ default: module.AuditPage }))
);
const CalendarPage = lazy(() =>
  import("./admin/pages/CalendarPage").then((module) => ({ default: module.CalendarPage }))
);
const KpiPage = lazy(() =>
  import("./admin/pages/KpiPage").then((module) => ({ default: module.KpiPage }))
);
const PackagesPage = lazy(() =>
  import("./admin/pages/PackagesPage").then((module) => ({ default: module.PackagesPage }))
);
const StudentsPage = lazy(() =>
  import("./admin/pages/StudentsPage").then((module) => ({ default: module.StudentsPage }))
);
const TeachersPage = lazy(() =>
  import("./admin/pages/TeachersPage").then((module) => ({ default: module.TeachersPage }))
);
const UsersPage = lazy(() =>
  import("./admin/pages/UsersPage").then((module) => ({ default: module.UsersPage }))
);

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

  const handleSignedIn = useCallback((tokenPair: TokenPair) => {
    saveTokenPair(tokenPair);
  }, []);

  const handleSignOut = useCallback(() => {
    void logout().catch(() => undefined);
    clearAccessSession();
  }, []);

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
        <Route path="users" element={<LazyAdminSection><UsersPage /></LazyAdminSection>} />
        <Route path="teachers" element={<LazyAdminSection><TeachersPage /></LazyAdminSection>} />
        <Route path="calendar" element={<LazyAdminSection><CalendarPage /></LazyAdminSection>} />
        <Route path="audit" element={<LazyAdminSection><AuditPage /></LazyAdminSection>} />
        <Route path="students" element={<LazyAdminSection><StudentsPage /></LazyAdminSection>} />
        <Route path="packages" element={<LazyAdminSection><PackagesPage /></LazyAdminSection>} />
        <Route path="kpi" element={<LazyAdminSection><KpiPage /></LazyAdminSection>} />
      </Route>
      <Route path="*" element={<Navigate to={tokens ? "/admin" : "/login"} replace />} />
    </Routes>
  );
}

type LazyAdminSectionProps = {
  children: ReactNode;
};

function LazyAdminSection({ children }: LazyAdminSectionProps) {
  return (
    <Suspense
      fallback={
        <article className="card section-page">
          <p className="eyebrow">Админка</p>
          <h1>Загрузка раздела...</h1>
          <p className="summary">Подгружаем код и данные выбранного раздела.</p>
        </article>
      }
    >
      {children}
    </Suspense>
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
      setError(submitError instanceof Error ? submitError.message : "Непредвиденная ошибка");
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
        <h1>Вход в админку</h1>
        <p className="summary">
          Авторизуйтесь для доступа к защищенным разделам админки. При отсутствии или
          невалидности сессии произойдет редирект сюда.
        </p>
      </section>

      <section className="card">
        {tokens === null ? (
          <form onSubmit={handleSubmit} className="auth-form">
            <label>
              <span>Почта</span>
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
              <span>Пароль</span>
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
              {pending ? "Входим..." : "Войти"}
            </button>

            {error ? <p className="error-text">{error}</p> : null}
          </form>
        ) : (
          <div className="auth-state">
            <p className="success-text">Вы авторизованы. Откройте защищенный раздел админки.</p>
            <p>
              <strong>Токен доступа:</strong> <code>{maskToken(tokens.access_token)}</code>
            </p>
            <p>
              <strong>Тип токена:</strong> <code>{tokens.token_type}</code>
            </p>
            <button type="button" onClick={handleLogout}>
              Выйти
            </button>
            <Link className="link-btn" to="/admin">
              Открыть админку
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
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    let active = true;

    setState("pending");
    getCurrentUser()
      .then((currentUser) => {
        if (!active) {
          return;
        }
        if (currentUser.role.name !== "admin") {
          setCurrentUser(null);
          onInvalidSession();
          setState("denied");
          return;
        }
        setCurrentUser(currentUser);
        setState("granted");
      })
      .catch(() => {
        if (!active) {
          return;
        }
        setCurrentUser(null);
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
          <h2>Проверяем сессию...</h2>
          <p className="summary">Проверяем токен и роль администратора.</p>
        </section>
      </main>
    );
  }

  return <CurrentUserProvider user={currentUser}>{children}</CurrentUserProvider>;
}
