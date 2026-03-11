import { FormEvent, useEffect, useMemo, useState } from "react";

import { getKpiOverview } from "../../features/kpi/api";
import type { KpiOverview } from "../../features/kpi/types";
import { listTeachers } from "../../features/teachers/api";
import type { TeacherListItem } from "../../features/teachers/types";
import { ApiClientError, apiClient } from "../../shared/api/client";
import type { PageResponse } from "../../shared/api/types";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);

type ProvisionRole = "teacher" | "admin";
type UserRoleFilter = "all" | "student" | "teacher" | "admin";
type UserActiveFilter = "all" | "active" | "inactive";

type ProvisionedTeacherProfile = {
  profile_id: string;
  display_name: string;
  status: string;
  verified: boolean;
};

type ProvisionedUser = {
  user_id: string;
  email: string;
  timezone: string;
  role: string;
  is_active: boolean;
  created_at_utc: string;
  updated_at_utc: string;
  teacher_profile?: ProvisionedTeacherProfile | null;
};

type AdminUserListItem = {
  user_id: string;
  email: string;
  timezone: string;
  role: "student" | "teacher" | "admin";
  is_active: boolean;
  teacher_profile_display_name?: string | null;
  created_at_utc: string;
  updated_at_utc: string;
};

function formatDateTime(value: string | null): string {
  if (!value) {
    return "—";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(parsed);
}

function toLocalizedError(error: unknown, fallback: string): string {
  if (error instanceof ApiClientError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

function buildUsersQuery(
  roleFilter: UserRoleFilter,
  activeFilter: UserActiveFilter,
  query: string
): string {
  const params = new URLSearchParams({
    limit: "50",
    offset: "0"
  });

  if (roleFilter !== "all") {
    params.set("role", roleFilter);
  }
  if (activeFilter === "active") {
    params.set("is_active", "true");
  }
  if (activeFilter === "inactive") {
    params.set("is_active", "false");
  }

  const normalizedQuery = query.trim();
  if (normalizedQuery) {
    params.set("q", normalizedQuery);
  }

  return params.toString();
}

export function UsersPage() {
  const [overview, setOverview] = useState<KpiOverview | null>(null);
  const [teachers, setTeachers] = useState<TeacherListItem[]>([]);
  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [teachersUnavailable, setTeachersUnavailable] = useState(false);
  const [usersUnavailable, setUsersUnavailable] = useState(false);

  const [userRoleFilter, setUserRoleFilter] = useState<UserRoleFilter>("all");
  const [userActiveFilter, setUserActiveFilter] = useState<UserActiveFilter>("all");
  const [userQuery, setUserQuery] = useState("");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [role, setRole] = useState<ProvisionRole>("teacher");
  const [displayName, setDisplayName] = useState("New Teacher");
  const [bio, setBio] = useState("");
  const [experienceYears, setExperienceYears] = useState("0");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [activeActionUserId, setActiveActionUserId] = useState<string | null>(null);
  const [lastProvisioned, setLastProvisioned] = useState<ProvisionedUser | null>(null);

  async function loadPageData() {
    setLoading(true);
    setError(null);
    setUsersError(null);
    setActionError(null);
    setTeachersUnavailable(false);
    setUsersUnavailable(false);

    const usersPath = `/admin/users?${buildUsersQuery(userRoleFilter, userActiveFilter, userQuery)}`;
    const [overviewResult, teachersResult, usersResult] = await Promise.allSettled([
      getKpiOverview(),
      listTeachers(),
      apiClient.request<PageResponse<AdminUserListItem>>(usersPath)
    ]);

    if (overviewResult.status === "fulfilled") {
      setOverview(overviewResult.value);
    } else {
      setOverview(null);
      setError(toLocalizedError(overviewResult.reason, "Не удалось загрузить сводку по ролям"));
    }

    if (teachersResult.status === "fulfilled") {
      setTeachers(teachersResult.value.items);
    } else {
      setTeachers([]);
      if (
        teachersResult.reason instanceof ApiClientError &&
        UNAVAILABLE_STATUSES.has(teachersResult.reason.status)
      ) {
        setTeachersUnavailable(true);
      } else {
        setError((current) =>
          current ??
          toLocalizedError(teachersResult.reason, "Не удалось загрузить список преподавателей")
        );
      }
    }

    if (usersResult.status === "fulfilled") {
      setUsers(usersResult.value.items);
      setUsersTotal(usersResult.value.total);
    } else {
      setUsers([]);
      setUsersTotal(0);
      if (
        usersResult.reason instanceof ApiClientError &&
        UNAVAILABLE_STATUSES.has(usersResult.reason.status)
      ) {
        setUsersUnavailable(true);
      } else {
        setUsersError(
          toLocalizedError(usersResult.reason, "Не удалось загрузить список пользователей")
        );
      }
    }

    setLoading(false);
  }

  useEffect(() => {
    void loadPageData();
  }, [userRoleFilter, userActiveFilter, userQuery]);

  const latestTeachers = useMemo(
    () =>
      [...teachers]
        .sort(
          (left, right) =>
            new Date(right.updated_at_utc).getTime() - new Date(left.updated_at_utc).getTime()
        )
        .slice(0, 12),
    [teachers]
  );

  async function handleProvision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setSubmitError(null);

    try {
      const payload: {
        email: string;
        password: string;
        timezone: string;
        role: ProvisionRole;
        teacher_profile?: {
          display_name: string;
          bio: string;
          experience_years: number;
        };
      } = {
        email: email.trim(),
        password,
        timezone: timezone.trim() || "UTC",
        role
      };

      if (role === "teacher") {
        payload.teacher_profile = {
          display_name: displayName.trim() || "Teacher",
          bio: bio.trim(),
          experience_years: Number(experienceYears) || 0
        };
      }

      const provisioned = await apiClient.request<ProvisionedUser>("/admin/users/provision", {
        method: "POST",
        body: payload
      });

      setLastProvisioned(provisioned);
      setEmail("");
      setPassword("");
      if (role === "teacher") {
        setDisplayName("New Teacher");
        setBio("");
        setExperienceYears("0");
      }

      await loadPageData();
    } catch (requestError) {
      setSubmitError(toLocalizedError(requestError, "Не удалось создать пользователя"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleUserActive(user: AdminUserListItem) {
    setActiveActionUserId(user.user_id);
    setActionError(null);
    const nextAction = user.is_active ? "deactivate" : "activate";

    try {
      await apiClient.request<AdminUserListItem>(`/admin/users/${user.user_id}/${nextAction}`, {
        method: "POST"
      });
      await loadPageData();
    } catch (requestError) {
      setActionError(
        toLocalizedError(
          requestError,
          user.is_active ? "Не удалось деактивировать пользователя" : "Не удалось активировать пользователя"
        )
      );
    } finally {
      setActiveActionUserId(null);
    }
  }

  if (loading && overview === null && users.length === 0 && teachers.length === 0) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Users</p>
        <h1>Пользователи</h1>
        <p className="summary">Загрузка данных...</p>
      </article>
    );
  }

  return (
    <section className="users-page">
      <article className="card section-page">
        <p className="eyebrow">Users</p>
        <h1>Управление пользователями</h1>
        <p className="summary">
          Здесь доступны счётчики ролей и создание повышенных ролей (`teacher`, `admin`) через
          защищенный `POST /admin/users/provision`.
        </p>
        <p className="summary">
          Аккаунты `student` создаются через публичную регистрацию (`/identity/auth/register`).
        </p>
        {error ? <p className="error-text">{error}</p> : null}
      </article>

      <article className="card">
        <h2>Сводка ролей</h2>
        {overview ? (
          <div className="users-metrics-grid">
            <div className="kpi-tile">
              <h3>Всего</h3>
              <p>{overview.users_total}</p>
            </div>
            <div className="kpi-tile">
              <h3>Учеников</h3>
              <p>{overview.users_students}</p>
            </div>
            <div className="kpi-tile">
              <h3>Преподавателей</h3>
              <p>{overview.users_teachers}</p>
            </div>
            <div className="kpi-tile">
              <h3>Админов</h3>
              <p>{overview.users_admins}</p>
            </div>
          </div>
        ) : (
          <p className="summary">Сводка по ролям недоступна.</p>
        )}
      </article>

      <article className="card">
        <h2>Список пользователей</h2>
        <div className="users-provision-form">
          <label>
            <span>Роль</span>
            <select
              value={userRoleFilter}
              onChange={(event) => setUserRoleFilter(event.target.value as UserRoleFilter)}
            >
              <option value="all">Все роли</option>
              <option value="student">student</option>
              <option value="teacher">teacher</option>
              <option value="admin">admin</option>
            </select>
          </label>

          <label>
            <span>Статус</span>
            <select
              value={userActiveFilter}
              onChange={(event) => setUserActiveFilter(event.target.value as UserActiveFilter)}
            >
              <option value="all">Все</option>
              <option value="active">Только активные</option>
              <option value="inactive">Только отключённые</option>
            </select>
          </label>

          <label>
            <span>Поиск (email / display name)</span>
            <input
              type="search"
              value={userQuery}
              onChange={(event) => setUserQuery(event.target.value)}
              placeholder="например, teacher@..."
            />
          </label>
        </div>

        <p className="summary">Найдено пользователей: {usersTotal}</p>
        {usersError ? <p className="error-text">{usersError}</p> : null}
        {actionError ? <p className="error-text">{actionError}</p> : null}

        {usersUnavailable ? (
          <p className="summary">
            `GET /admin/users` и операции активации/деактивации пока недоступны в backend.
          </p>
        ) : users.length === 0 ? (
          <p className="summary">Пользователи не найдены по выбранным фильтрам.</p>
        ) : (
          <div className="bookings-table-wrap">
            <table className="bookings-table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Роль</th>
                  <th>Статус</th>
                  <th>Таймзона</th>
                  <th>Teacher profile</th>
                  <th>Обновлён</th>
                  <th>Действие</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.user_id}>
                    <td>{user.email}</td>
                    <td>{user.role}</td>
                    <td>{user.is_active ? "Активен" : "Отключён"}</td>
                    <td>{user.timezone}</td>
                    <td>{user.teacher_profile_display_name || "—"}</td>
                    <td>{formatDateTime(user.updated_at_utc)}</td>
                    <td>
                      <button
                        type="button"
                        disabled={activeActionUserId === user.user_id}
                        onClick={() => void handleToggleUserActive(user)}
                      >
                        {activeActionUserId === user.user_id
                          ? "Выполняется..."
                          : user.is_active
                            ? "Деактивировать"
                            : "Активировать"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </article>

      <article className="card">
        <h2>Создать пользователя (teacher/admin)</h2>
        <form className="users-provision-form" onSubmit={handleProvision}>
          <label>
            <span>Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="off"
            />
          </label>

          <label>
            <span>Пароль</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
            />
          </label>

          <label>
            <span>Таймзона</span>
            <input
              type="text"
              required
              value={timezone}
              onChange={(event) => setTimezone(event.target.value)}
            />
          </label>

          <label>
            <span>Роль</span>
            <select value={role} onChange={(event) => setRole(event.target.value as ProvisionRole)}>
              <option value="teacher">teacher</option>
              <option value="admin">admin</option>
            </select>
          </label>

          {role === "teacher" ? (
            <div className="users-teacher-fields">
              <label>
                <span>Display name</span>
                <input
                  type="text"
                  required
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                />
              </label>
              <label>
                <span>Bio</span>
                <textarea value={bio} onChange={(event) => setBio(event.target.value)} rows={3} />
              </label>
              <label>
                <span>Опыт (лет)</span>
                <input
                  type="number"
                  min={0}
                  max={80}
                  value={experienceYears}
                  onChange={(event) => setExperienceYears(event.target.value)}
                />
              </label>
            </div>
          ) : null}

          <button type="submit" disabled={submitting}>
            {submitting ? "Создание..." : "Создать пользователя"}
          </button>
          {submitError ? <p className="error-text">{submitError}</p> : null}
        </form>

        {lastProvisioned ? (
          <div className="users-last-provision">
            <p className="success-text">Пользователь создан успешно.</p>
            <p>
              <strong>Email:</strong> {lastProvisioned.email}
            </p>
            <p>
              <strong>Role:</strong> {lastProvisioned.role}
            </p>
            <p>
              <strong>User ID:</strong> {lastProvisioned.user_id}
            </p>
            <p>
              <strong>Created:</strong> {formatDateTime(lastProvisioned.created_at_utc)}
            </p>
          </div>
        ) : null}
      </article>

      <article className="card">
        <h2>Преподаватели (последние обновления)</h2>
        {teachersUnavailable ? (
          <p className="summary">`GET /admin/teachers` пока недоступен в текущем backend-контракте.</p>
        ) : latestTeachers.length === 0 ? (
          <p className="summary">Список преподавателей пуст.</p>
        ) : (
          <div className="users-teachers-list">
            {latestTeachers.map((teacher) => (
              <article key={teacher.teacher_id} className="users-teacher-item">
                <p>
                  <strong>{teacher.display_name}</strong>
                </p>
                <p>{teacher.email}</p>
                <p>
                  {teacher.status} {teacher.verified ? "• verified" : "• pending"}
                </p>
                <p>{formatDateTime(teacher.updated_at_utc)}</p>
              </article>
            ))}
          </div>
        )}
      </article>
    </section>
  );
}
