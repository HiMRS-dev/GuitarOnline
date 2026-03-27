import { useCallback, useEffect, useMemo, useState } from "react";

import { getCurrentUser } from "../../features/auth/api";
import { getKpiOverview } from "../../features/kpi/api";
import type { KpiOverview } from "../../features/kpi/types";
import { listTeachers } from "../../features/teachers/api";
import type { TeacherListItem } from "../../features/teachers/types";
import { ApiClientError, apiClient } from "../../shared/api/client";
import type { PageResponse } from "../../shared/api/types";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);
const PRIVILEGED_ADMIN_EMAIL = "bootstrap-admin@guitaronline.dev";

type UserRole = "student" | "teacher" | "admin";
type UserRoleFilter = "all" | UserRole;
type UserActiveFilter = "all" | "active" | "inactive";

type AdminUserListItem = {
  user_id: string;
  email: string;
  full_name: string;
  timezone: string;
  role: UserRole;
  is_active: boolean;
  teacher_profile_display_name?: string | null;
  created_at_utc: string;
  updated_at_utc: string;
};

const ROLE_LABELS: Record<UserRole, string> = {
  student: "студент",
  teacher: "преподаватель",
  admin: "администратор"
};

const TEACHER_STATUS_LABELS: Record<string, string> = {
  active: "активен",
  disabled: "отключен"
};

function formatRole(role: string): string {
  return ROLE_LABELS[role as UserRole] ?? role;
}

function formatTeacherStatus(status: string): string {
  return TEACHER_STATUS_LABELS[status] ?? status;
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "-";
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

function buildRoleDrafts(items: AdminUserListItem[]): Record<string, UserRole> {
  const drafts: Record<string, UserRole> = {};
  for (const item of items) {
    drafts[item.user_id] = item.role;
  }
  return drafts;
}

function normalizeEmail(value: string | null): string {
  return value?.trim().toLowerCase() ?? "";
}

export function UsersPage() {
  const [overview, setOverview] = useState<KpiOverview | null>(null);
  const [teachers, setTeachers] = useState<TeacherListItem[]>([]);
  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [currentAdminEmail, setCurrentAdminEmail] = useState<string | null>(null);
  const [userRoleDrafts, setUserRoleDrafts] = useState<Record<string, UserRole>>({});
  const [usersTotal, setUsersTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [teachersUnavailable, setTeachersUnavailable] = useState(false);
  const [usersUnavailable, setUsersUnavailable] = useState(false);

  const [userRoleFilter, setUserRoleFilter] = useState<UserRoleFilter>("all");
  const [userActiveFilter, setUserActiveFilter] = useState<UserActiveFilter>("all");
  const [userQuery, setUserQuery] = useState("");

  const [actionError, setActionError] = useState<string | null>(null);
  const [activeToggleUserId, setActiveToggleUserId] = useState<string | null>(null);
  const [activeRoleUserId, setActiveRoleUserId] = useState<string | null>(null);

  const loadPageData = useCallback(async () => {
    setLoading(true);
    setError(null);
    setUsersError(null);
    setActionError(null);
    setTeachersUnavailable(false);
    setUsersUnavailable(false);

    const usersPath = `/admin/users?${buildUsersQuery(userRoleFilter, userActiveFilter, userQuery)}`;
    const [overviewResult, teachersResult, usersResult, currentUserResult] = await Promise.allSettled([
      getKpiOverview(),
      listTeachers(),
      apiClient.request<PageResponse<AdminUserListItem>>(usersPath),
      getCurrentUser()
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
      setUserRoleDrafts(buildRoleDrafts(usersResult.value.items));
      setUsersTotal(usersResult.value.total);
    } else {
      setUsers([]);
      setUserRoleDrafts({});
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

    if (currentUserResult.status === "fulfilled") {
      setCurrentAdminEmail(currentUserResult.value.email);
    } else {
      setCurrentAdminEmail(null);
    }

    setLoading(false);
  }, [userRoleFilter, userActiveFilter, userQuery]);

  useEffect(() => {
    void loadPageData();
  }, [loadPageData]);

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
  const canManageAdminRoles =
    normalizeEmail(currentAdminEmail) === normalizeEmail(PRIVILEGED_ADMIN_EMAIL);

  function handleRoleDraftChange(userId: string, role: UserRole) {
    setUserRoleDrafts((current) => ({
      ...current,
      [userId]: role
    }));
  }

  async function handleChangeUserRole(user: AdminUserListItem) {
    const nextRole = userRoleDrafts[user.user_id] ?? user.role;
    if (nextRole === user.role) {
      return;
    }

    setActiveRoleUserId(user.user_id);
    setActionError(null);

    try {
      await apiClient.request<AdminUserListItem>(`/admin/users/${user.user_id}/role`, {
        method: "POST",
        body: { role: nextRole }
      });
      await loadPageData();
    } catch (requestError) {
      setActionError(toLocalizedError(requestError, "Не удалось изменить роль пользователя"));
    } finally {
      setActiveRoleUserId(null);
    }
  }

  async function handleToggleUserActive(user: AdminUserListItem) {
    setActiveToggleUserId(user.user_id);
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
          user.is_active
            ? "Не удалось деактивировать пользователя"
            : "Не удалось активировать пользователя"
        )
      );
    } finally {
      setActiveToggleUserId(null);
    }
  }

  if (loading && overview === null && users.length === 0 && teachers.length === 0) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Пользователи</p>
        <h1>Пользователи</h1>
        <p className="summary">Загрузка данных...</p>
      </article>
    );
  }

  return (
    <section className="users-page">
      <article className="card section-page">
        <p className="eyebrow">Пользователи</p>
        <h1>Управление пользователями</h1>
        <p className="summary">
          Публичная регистрация всегда создаёт аккаунт `student`. Повышенные роли назначаются
          только админом для уже существующих аккаунтов через `POST /admin/users/&lt;user_id&gt;/role`.
        </p>
        <p className="summary">
          При переводе пользователя в `teacher` backend автоматически создаёт или возвращает его
          профиль преподавателя в активное состояние.
        </p>
        {canManageAdminRoles ? null : (
          <p className="summary">
            Назначать и снимать роль администратора может только{" "}
            <code>{PRIVILEGED_ADMIN_EMAIL}</code>.
          </p>
        )}
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
              <option value="student">студент</option>
              <option value="teacher">преподаватель</option>
              <option value="admin">администратор</option>
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
              <option value="inactive">Только отключенные</option>
            </select>
          </label>

          <label>
            <span>Поиск (почта / ФИО / имя)</span>
            <input
              type="search"
              value={userQuery}
              onChange={(event) => setUserQuery(event.target.value)}
              placeholder="например, teacher@... или Иванов"
            />
          </label>
        </div>

        <p className="summary">Найдено пользователей: {usersTotal}</p>
        {usersError ? <p className="error-text">{usersError}</p> : null}
        {actionError ? <p className="error-text">{actionError}</p> : null}

        {usersUnavailable ? (
          <p className="summary">
            `GET /admin/users` и операции управления ролями пока недоступны в backend.
          </p>
        ) : users.length === 0 ? (
          <p className="summary">Пользователи не найдены по выбранным фильтрам.</p>
        ) : (
          <div className="bookings-table-wrap">
            <table className="bookings-table">
              <thead>
                <tr>
                  <th>Почта</th>
                  <th>ФИО</th>
                  <th>Роль</th>
                  <th>Статус</th>
                  <th>Таймзона</th>
                  <th>Профиль преподавателя</th>
                  <th>Обновлен</th>
                  <th>Управление</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => {
                  const draftRole = userRoleDrafts[user.user_id] ?? user.role;
                  const touchesAdminRole = user.role === "admin" || draftRole === "admin";
                  const canEditRole = canManageAdminRoles || !touchesAdminRole;
                  const roleChanged = draftRole !== user.role;
                  const toggleInProgress = activeToggleUserId === user.user_id;
                  const roleInProgress = activeRoleUserId === user.user_id;

                  return (
                    <tr key={user.user_id}>
                      <td>{user.email}</td>
                      <td>{user.full_name}</td>
                      <td>{formatRole(user.role)}</td>
                      <td>{user.is_active ? "Активен" : "Отключен"}</td>
                      <td>{user.timezone}</td>
                      <td>{user.teacher_profile_display_name || "-"}</td>
                      <td>{formatDateTime(user.updated_at_utc)}</td>
                      <td>
                        <div className="users-teacher-fields">
                          <label>
                            <span>Новая роль</span>
                            <select
                              value={draftRole}
                              disabled={roleInProgress || toggleInProgress || !canEditRole}
                              onChange={(event) =>
                                handleRoleDraftChange(user.user_id, event.target.value as UserRole)
                              }
                            >
                              <option value="student">студент</option>
                              <option value="teacher">преподаватель</option>
                              {canManageAdminRoles || user.role === "admin" ? (
                                <option value="admin">администратор</option>
                              ) : null}
                            </select>
                          </label>

                          <button
                            type="button"
                            disabled={!roleChanged || roleInProgress || toggleInProgress || !canEditRole}
                            onClick={() => void handleChangeUserRole(user)}
                          >
                            {roleInProgress ? "Сохраняю..." : "Сменить роль"}
                          </button>

                          <button
                            type="button"
                            disabled={toggleInProgress || roleInProgress}
                            onClick={() => void handleToggleUserActive(user)}
                          >
                            {toggleInProgress
                              ? "Выполняется..."
                              : user.is_active
                                ? "Деактивировать"
                                : "Активировать"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
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
                <p>{teacher.full_name}</p>
                <p>{teacher.email}</p>
                <p>{formatTeacherStatus(teacher.status)}</p>
                <p>{formatDateTime(teacher.updated_at_utc)}</p>
              </article>
            ))}
          </div>
        )}
      </article>
    </section>
  );
}
