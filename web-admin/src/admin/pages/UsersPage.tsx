import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";

import { useCurrentUser } from "../../features/auth/currentUser";
import { getKpiOverview, invalidateKpiOverviewCache } from "../../features/kpi/api";
import type { KpiOverview } from "../../features/kpi/types";
import { invalidateTeachersCache, listTeachers } from "../../features/teachers/api";
import type { TeacherListItem } from "../../features/teachers/types";
import { ApiClientError, apiClient } from "../../shared/api/client";
import type { PageResponse } from "../../shared/api/types";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);
const PRIVILEGED_ADMIN_EMAIL = "bootstrap-admin@guitaronline.dev";

type UserRole = "student" | "teacher" | "admin";
type UserRoleFilter = "all" | UserRole;
type UserActiveFilter = "all" | "active" | "inactive";

const ROLE_FILTER_OPTIONS: Array<{ value: UserRoleFilter; label: string }> = [
  { value: "all", label: "Все роли" },
  { value: "student", label: "студент" },
  { value: "teacher", label: "преподаватель" },
  { value: "admin", label: "админ" }
];

const ACTIVE_FILTER_OPTIONS: Array<{ value: UserActiveFilter; label: string }> = [
  { value: "all", label: "Все" },
  { value: "active", label: "Только активные" },
  { value: "inactive", label: "Только отключенные" }
];

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
  admin: "админ"
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

async function copyTextToClipboard(value: string): Promise<void> {
  if (typeof window !== "undefined" && window.isSecureContext && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  if (typeof document === "undefined") {
    throw new Error("Clipboard API is unavailable");
  }

  const fallbackInput = document.createElement("textarea");
  fallbackInput.value = value;
  fallbackInput.setAttribute("readonly", "true");
  fallbackInput.style.position = "fixed";
  fallbackInput.style.left = "-9999px";
  fallbackInput.style.top = "0";
  fallbackInput.style.opacity = "0";

  document.body.appendChild(fallbackInput);
  fallbackInput.focus();
  fallbackInput.select();

  const copied = document.execCommand("copy");
  document.body.removeChild(fallbackInput);

  if (!copied) {
    throw new Error("Clipboard fallback failed");
  }
}

export function UsersPage() {
  const currentAdmin = useCurrentUser();
  const [overview, setOverview] = useState<KpiOverview | null>(null);
  const [teachers, setTeachers] = useState<TeacherListItem[]>([]);
  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [revealedValueKey, setRevealedValueKey] = useState<string | null>(null);
  const [copyNotice, setCopyNotice] = useState<{
    key: string;
    message: string;
    tone: "success" | "error";
  } | null>(null);
  const [userRoleDrafts, setUserRoleDrafts] = useState<Record<string, UserRole>>({});
  const [usersTotal, setUsersTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [teachersLoading, setTeachersLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [teachersUnavailable, setTeachersUnavailable] = useState(false);
  const [usersUnavailable, setUsersUnavailable] = useState(false);

  const [userRoleFilter, setUserRoleFilter] = useState<UserRoleFilter>("all");
  const [userActiveFilter, setUserActiveFilter] = useState<UserActiveFilter>("all");
  const [userQuery, setUserQuery] = useState("");
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [selectedUserProfile, setSelectedUserProfile] = useState<AdminUserListItem | null>(null);
  const deferredUserQuery = useDeferredValue(userQuery);
  const [secondaryBootstrapped, setSecondaryBootstrapped] = useState(false);

  const [actionError, setActionError] = useState<string | null>(null);
  const [activeToggleUserId, setActiveToggleUserId] = useState<string | null>(null);
  const [activeRoleUserId, setActiveRoleUserId] = useState<string | null>(null);

  const loadUsersData = useCallback(async () => {
    setLoading(true);
    setUsersError(null);
    setActionError(null);
    setRevealedValueKey(null);
    setUsersUnavailable(false);

    const usersPath = `/admin/users?${buildUsersQuery(userRoleFilter, userActiveFilter, deferredUserQuery)}`;

    try {
      const page = await apiClient.request<PageResponse<AdminUserListItem>>(usersPath);
      setUsers(page.items);
      setUserRoleDrafts(buildRoleDrafts(page.items));
      setUsersTotal(page.total);
    } catch (requestError) {
      setUsers([]);
      setUserRoleDrafts({});
      setUsersTotal(0);

      if (requestError instanceof ApiClientError && UNAVAILABLE_STATUSES.has(requestError.status)) {
        setUsersUnavailable(true);
      } else {
        setUsersError(
          toLocalizedError(requestError, "Не удалось загрузить список пользователей")
        );
      }
    } finally {
      setLoading(false);
    }
  }, [userRoleFilter, userActiveFilter, deferredUserQuery]);

  const loadSecondaryData = useCallback(
    async ({ showLoading = false }: { showLoading?: boolean } = {}) => {
      if (showLoading) {
        setOverviewLoading(true);
        setTeachersLoading(true);
      }
      setError(null);
      setTeachersUnavailable(false);

      const [overviewResult, teachersResult] = await Promise.allSettled([
        getKpiOverview(),
        listTeachers()
      ]);

      let nextError: string | null = null;

      if (overviewResult.status === "fulfilled") {
        setOverview(overviewResult.value);
      } else {
        nextError = toLocalizedError(overviewResult.reason, "Не удалось загрузить сводку по ролям");
      }
      setOverviewLoading(false);

      if (teachersResult.status === "fulfilled") {
        setTeachers(teachersResult.value.items);
      } else if (
        teachersResult.reason instanceof ApiClientError &&
        UNAVAILABLE_STATUSES.has(teachersResult.reason.status)
      ) {
        setTeachersUnavailable(true);
        setTeachers([]);
      } else {
        setTeachers([]);
        nextError =
          nextError ??
          toLocalizedError(teachersResult.reason, "Не удалось загрузить список преподавателей");
      }
      setTeachersLoading(false);
      setError(nextError);
    },
    []
  );

  useEffect(() => {
    void loadUsersData();
  }, [loadUsersData]);

  useEffect(() => {
    if (secondaryBootstrapped || loading) {
      return;
    }
    setSecondaryBootstrapped(true);
    void loadSecondaryData({ showLoading: true });
  }, [secondaryBootstrapped, loading, loadSecondaryData]);

  useEffect(() => {
    if (copyNotice === null) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setCopyNotice(null);
    }, 1600);

    return () => window.clearTimeout(timeoutId);
  }, [copyNotice]);

  useEffect(() => {
    if (!selectedUserId) {
      setSelectedUserProfile(null);
      return;
    }
    const selectedFromList = users.find((item) => item.user_id === selectedUserId);
    if (selectedFromList) {
      setSelectedUserProfile(selectedFromList);
    }
  }, [selectedUserId, users]);

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

  const selectedUser = useMemo(() => {
    if (!selectedUserId) {
      return null;
    }
    const fromList = users.find((item) => item.user_id === selectedUserId) ?? null;
    if (fromList) {
      return fromList;
    }
    if (selectedUserProfile && selectedUserProfile.user_id === selectedUserId) {
      return selectedUserProfile;
    }
    return null;
  }, [selectedUserId, selectedUserProfile, users]);

  const userSuggestions = useMemo(() => {
    if (!userQuery.trim()) {
      return [];
    }
    return users.slice(0, 6);
  }, [userQuery, users]);

  const canManageAdminRoles =
    normalizeEmail(currentAdmin?.email ?? null) === normalizeEmail(PRIVILEGED_ADMIN_EMAIL);

  function handleRoleDraftChange(userId: string, role: UserRole) {
    setUserRoleDrafts((current) => ({
      ...current,
      [userId]: role
    }));
  }

  async function handleCopyEmail(email: string, noticeKey: string) {
    try {
      await copyTextToClipboard(email);
      setCopyNotice({
        key: noticeKey,
        message: "Почта скопирована",
        tone: "success"
      });
    } catch {
      setCopyNotice({
        key: noticeKey,
        message: "Не удалось скопировать почту",
        tone: "error"
      });
    }
  }

  async function handleCopyFullName(fullName: string, noticeKey: string) {
    try {
      await copyTextToClipboard(fullName);
      setCopyNotice({
        key: noticeKey,
        message: "ФИО скопировано",
        tone: "success"
      });
    } catch {
      setCopyNotice({
        key: noticeKey,
        message: "Не удалось скопировать ФИО",
        tone: "error"
      });
    }
  }

  function renderRevealableValue(
    value: string,
    label: string,
    valueKey: string,
    options?: {
      onClick?: () => void;
      notice?: { message: string; tone: "success" | "error" } | null;
    }
  ) {
    const isExpanded = revealedValueKey === valueKey;
    const normalizedValue = value || "-";

    return (
      <div className="users-reveal">
        <button
          type="button"
          className={`users-reveal-trigger${isExpanded ? " is-expanded" : ""}`}
          aria-expanded={isExpanded}
          aria-label={isExpanded ? `Скрыть ${label}` : `Показать ${label} полностью`}
          onClick={() => {
            options?.onClick?.();
            setRevealedValueKey((current) => (current === valueKey ? null : valueKey));
          }}
        >
          <span className={`users-reveal-text${isExpanded ? " is-expanded" : ""}`}>
            {normalizedValue}
          </span>
        </button>
        {options?.notice ? (
          <span
            className={`users-inline-notice${options.notice.tone === "error" ? " is-error" : ""}`}
            role="status"
            aria-live="polite"
          >
            {options.notice.message}
          </span>
        ) : null}
      </div>
    );
  }

  async function handleChangeUserRole(user: AdminUserListItem) {
    const nextRole = userRoleDrafts[user.user_id] ?? user.role;
    if (nextRole === user.role) {
      return;
    }

    setActiveRoleUserId(user.user_id);
    setActionError(null);

    try {
      invalidateKpiOverviewCache();
      invalidateTeachersCache();
      await apiClient.request<AdminUserListItem>(`/admin/users/${user.user_id}/role`, {
        method: "POST",
        body: { role: nextRole }
      });
      await loadUsersData();
      void loadSecondaryData();
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
      invalidateKpiOverviewCache();
      invalidateTeachersCache();
      await apiClient.request<AdminUserListItem>(`/admin/users/${user.user_id}/${nextAction}`, {
        method: "POST"
      });
      await loadUsersData();
      void loadSecondaryData();
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

  if (loading && users.length === 0) {
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
            Назначать и снимать роль админа может только <code>{PRIVILEGED_ADMIN_EMAIL}</code>.
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
        ) : overviewLoading ? (
          <p className="summary">Загружаем сводку...</p>
        ) : (
          <p className="summary">Сводка по ролям недоступна.</p>
        )}
      </article>

      <article className="card">
        <h2>Список пользователей</h2>
        <div className="users-provision-form">
          <label className="teachers-picker-search">
            <span>Search (email / full name / username)</span>
            <input
              type="search"
              value={userQuery}
              onChange={(event) => setUserQuery(event.target.value)}
              placeholder="for example, teacher@... or Ivanov"
            />
          </label>
          {userQuery.trim() ? (
            <div className="picker-search-suggestions">
              {loading ? <p className="summary">Loading suggestions...</p> : null}
              {!loading && !usersUnavailable && userSuggestions.length ? (
                <div className="picker-suggestion-list">
                  {userSuggestions.map((user) => (
                    <div key={user.user_id} className="picker-suggestion-item">
                      <div className="picker-suggestion-meta">
                        <strong>{user.full_name}</strong>
                        <span>{user.email}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedUserId(user.user_id);
                          setSelectedUserProfile(user);
                          setUserQuery(user.email);
                        }}
                      >
                        Select
                      </button>
                    </div>
                  ))}
                </div>
              ) : null}
              {!loading && !usersUnavailable && !usersError && userSuggestions.length === 0 ? (
                <p className="summary">No matches found.</p>
              ) : null}
            </div>
          ) : null}

          <div className="quick-filter-group" role="group" aria-label="User role filters">
            {ROLE_FILTER_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={userRoleFilter === option.value ? "quick-filter active" : "quick-filter"}
                onClick={() => setUserRoleFilter(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className="quick-filter-group" role="group" aria-label="User status filters">
            {ACTIVE_FILTER_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={userActiveFilter === option.value ? "quick-filter active" : "quick-filter"}
                onClick={() => setUserActiveFilter(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className="quick-filter-group" role="group" aria-label="User selection actions">
            <button
              type="button"
              className="quick-filter"
              disabled={!selectedUserId && !userQuery.trim()}
              onClick={() => {
                setSelectedUserId(null);
                setSelectedUserProfile(null);
                setUserQuery("");
              }}
            >
              Clear selection
            </button>
          </div>
        </div>

        <p className="summary">
          Selected: <strong>{selectedUser?.full_name ?? selectedUser?.email ?? "not selected"}</strong>
        </p>

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
            <table className="bookings-table users-table">
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
                    <tr
                      key={user.user_id}
                      className={selectedUserId === user.user_id ? "users-table-row-active" : undefined}
                    >
                      <td className="users-table-cell-compact">
                        {renderRevealableValue(user.email, "почту", `email:${user.user_id}`, {
                          onClick: () => {
                            void handleCopyEmail(user.email, `email:${user.user_id}`);
                          },
                          notice:
                            copyNotice?.key === `email:${user.user_id}`
                              ? {
                                  message: copyNotice.message,
                                  tone: copyNotice.tone
                                }
                              : null
                        })}
                      </td>
                      <td className="users-table-cell-compact">
                        {renderRevealableValue(user.full_name, "ФИО", `full-name:${user.user_id}`, {
                          onClick: () => {
                            void handleCopyFullName(user.full_name, `full-name:${user.user_id}`);
                          },
                          notice:
                            copyNotice?.key === `full-name:${user.user_id}`
                              ? {
                                  message: copyNotice.message,
                                  tone: copyNotice.tone
                                }
                              : null
                        })}
                      </td>
                      <td className="users-table-cell-compact">
                        {renderRevealableValue(formatRole(user.role), "роль", `role:${user.user_id}`)}
                      </td>
                      <td className="users-table-cell-compact">
                        {renderRevealableValue(
                          user.is_active ? "Активен" : "Отключен",
                          "статус",
                          `status:${user.user_id}`
                        )}
                      </td>
                      <td className="users-table-cell-compact">
                        {renderRevealableValue(user.timezone, "таймзону", `timezone:${user.user_id}`)}
                      </td>
                      <td className="users-table-cell-compact">
                        {renderRevealableValue(
                          user.teacher_profile_display_name || "-",
                          "профиль преподавателя",
                          `teacher-profile:${user.user_id}`
                        )}
                      </td>
                      <td className="users-table-cell-compact">
                        {renderRevealableValue(
                          formatDateTime(user.updated_at_utc),
                          "дату обновления",
                          `updated-at:${user.user_id}`
                        )}
                      </td>
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
                                <option value="admin">админ</option>
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
        ) : teachersLoading ? (
          <p className="summary">Загружаем последние обновления...</p>
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
