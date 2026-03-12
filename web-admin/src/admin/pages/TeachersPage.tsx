import { useEffect, useMemo, useState } from "react";

import { ApiClientError } from "../../shared/api/client";
import {
  disableTeacher,
  getTeacherDetail,
  listTeachers,
  verifyTeacher
} from "../../features/teachers/api";
import type { TeacherDetail, TeacherListItem } from "../../features/teachers/types";
import {
  ADMIN_TEACHERS_STATUS_STORAGE_KEY,
  ADMIN_TEACHER_FILTER_STORAGE_KEY
} from "../../shared/storage/adminFilters";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);
type TeacherStatusFilter = "all" | "pending" | "verified" | "disabled";

const STATUS_FILTER_OPTIONS: Array<{ value: TeacherStatusFilter; label: string }> = [
  { value: "all", label: "Все" },
  { value: "verified", label: "Подтверждённые" },
  { value: "pending", label: "На проверке" },
  { value: "disabled", label: "Отключённые" }
];

const TEACHER_STATUS_LABELS: Record<string, string> = {
  pending: "на проверке",
  verified: "подтверждён",
  disabled: "отключён"
};

function normalizeStatusFilter(value: string | null): TeacherStatusFilter {
  if (value === "pending" || value === "verified" || value === "disabled") {
    return value;
  }
  return "all";
}

function formatTeacherStatus(status: string): string {
  return TEACHER_STATUS_LABELS[status] ?? status;
}

function isValidTeacherStatusFilter(value: string, filter: TeacherStatusFilter): boolean {
  return filter === "all" || value === filter;
}

export function TeachersPage() {
  const [teachers, setTeachers] = useState<TeacherListItem[]>([]);
  const [selectedTeacherId, setSelectedTeacherId] = useState<string | null>(
    () => localStorage.getItem(ADMIN_TEACHER_FILTER_STORAGE_KEY) || null
  );
  const [statusFilter, setStatusFilter] = useState<TeacherStatusFilter>(() =>
    normalizeStatusFilter(localStorage.getItem(ADMIN_TEACHERS_STATUS_STORAGE_KEY))
  );
  const [teacherDetail, setTeacherDetail] = useState<TeacherDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionPending, setActionPending] = useState<"verify" | "disable" | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setUnavailable(false);

    listTeachers(statusFilter === "all" ? {} : { status: statusFilter })
      .then((page) => {
        if (!active) {
          return;
        }
        setTeachers(page.items);
        setSelectedTeacherId((currentSelectedTeacherId) => {
          const preferredTeacherId = currentSelectedTeacherId ?? page.items[0]?.teacher_id ?? null;
          const hasPreferredTeacher = page.items.some(
            (teacher) => teacher.teacher_id === preferredTeacherId
          );
          return hasPreferredTeacher ? preferredTeacherId : page.items[0]?.teacher_id ?? null;
        });
      })
      .catch((requestError) => {
        if (!active) {
          return;
        }
        if (
          requestError instanceof ApiClientError &&
          UNAVAILABLE_STATUSES.has(requestError.status)
        ) {
          setUnavailable(true);
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "Не удалось загрузить список");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [statusFilter]);

  useEffect(() => {
    if (!selectedTeacherId) {
      localStorage.removeItem(ADMIN_TEACHER_FILTER_STORAGE_KEY);
      return;
    }
    localStorage.setItem(ADMIN_TEACHER_FILTER_STORAGE_KEY, selectedTeacherId);
  }, [selectedTeacherId]);

  useEffect(() => {
    localStorage.setItem(ADMIN_TEACHERS_STATUS_STORAGE_KEY, statusFilter);
  }, [statusFilter]);

  useEffect(() => {
    if (!selectedTeacherId || unavailable) {
      setTeacherDetail(null);
      return;
    }

    let active = true;
    setDetailError(null);
    setDetailLoading(true);

    getTeacherDetail(selectedTeacherId)
      .then((detail) => {
        if (active) {
          setTeacherDetail(detail);
        }
      })
      .catch((requestError) => {
        if (active) {
          setDetailError(requestError instanceof Error ? requestError.message : "Не удалось загрузить данные");
        }
      })
      .finally(() => {
        if (active) {
          setDetailLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [selectedTeacherId, unavailable]);

  const selectedTeacher = useMemo(
    () => teachers.find((item) => item.teacher_id === selectedTeacherId) ?? null,
    [selectedTeacherId, teachers]
  );

  async function refreshTeachersAndSelection(preferredTeacherId: string | null) {
    const page = await listTeachers(statusFilter === "all" ? {} : { status: statusFilter });
    setTeachers(page.items);

    const fallbackTeacherId = preferredTeacherId ?? page.items[0]?.teacher_id ?? null;
    const nextSelectedId = page.items.some((item) => item.teacher_id === fallbackTeacherId)
      ? fallbackTeacherId
      : page.items[0]?.teacher_id ?? null;

    setSelectedTeacherId(nextSelectedId);
    if (!nextSelectedId) {
      setTeacherDetail(null);
    }
  }

  async function handleModerationAction(action: "verify" | "disable") {
    if (!selectedTeacherId) {
      return;
    }

    setActionPending(action);
    setActionError(null);
    setActionSuccess(null);

    try {
      const updatedDetail =
        action === "verify"
          ? await verifyTeacher(selectedTeacherId)
          : await disableTeacher(selectedTeacherId);

      setTeacherDetail(updatedDetail);
      await refreshTeachersAndSelection(updatedDetail.teacher_id);

      if (!isValidTeacherStatusFilter(updatedDetail.status, statusFilter)) {
        setActionSuccess("Статус обновлён. Преподаватель скрыт текущим фильтром.");
      } else {
        setActionSuccess(
          action === "verify"
            ? "Преподаватель подтверждён."
            : "Преподаватель отключён и вход заблокирован."
        );
      }
    } catch (requestError) {
      setActionError(
        requestError instanceof Error
          ? requestError.message
          : action === "verify"
            ? "Не удалось подтвердить преподавателя"
            : "Не удалось отключить преподавателя"
      );
    } finally {
      setActionPending(null);
    }
  }

  if (unavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Преподаватели</p>
        <h1>Эндпоинты недоступны</h1>
        <p className="summary">
          Для этого раздела нужны <code>GET /admin/teachers</code>, <code>GET /admin/teachers/{`{id}`}</code>,
          <code>POST /admin/teachers/{`{id}`}/verify</code>, <code>POST /admin/teachers/{`{id}`}/disable</code>.
        </p>
      </article>
    );
  }

  if (loading) {
    return (
      <article className="card section-page">
        <h1>Преподаватели</h1>
        <p className="summary">Загрузка списка...</p>
      </article>
    );
  }

  if (error) {
    return (
      <article className="card section-page">
        <h1>Преподаватели</h1>
        <p className="error-text">{error}</p>
      </article>
    );
  }

  return (
    <section className="teachers-grid">
      <article className="card">
        <p className="eyebrow">Преподаватели</p>
        <h1>Список преподавателей</h1>
        <div className="quick-filter-group" role="group" aria-label="Фильтры статуса преподавателей">
          {STATUS_FILTER_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              className={statusFilter === option.value ? "quick-filter active" : "quick-filter"}
              onClick={() => setStatusFilter(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        {teachers.length === 0 ? (
          <p className="summary">По выбранному фильтру нет преподавателей.</p>
        ) : (
          <div className="teacher-list">
            {teachers.map((teacher) => (
              <button
                key={teacher.teacher_id}
                type="button"
                className={
                  teacher.teacher_id === selectedTeacherId ? "teacher-item active" : "teacher-item"
                }
                onClick={() => setSelectedTeacherId(teacher.teacher_id)}
              >
                <strong>{teacher.display_name}</strong>
                <span>{teacher.email}</span>
                <span>
                  {formatTeacherStatus(teacher.status)}{" "}
                  {teacher.verified ? "• подтверждён" : "• на проверке"}
                </span>
              </button>
            ))}
          </div>
        )}
      </article>

      <article className="card">
        <p className="eyebrow">Карточка преподавателя</p>
        {selectedTeacher ? <h1>{selectedTeacher.display_name}</h1> : <h1>Не выбрано</h1>}

        <div className="quick-filter-group" role="group" aria-label="Действия модерации">
          <button
            type="button"
            className="quick-filter"
            disabled={
              !teacherDetail ||
              actionPending !== null ||
              teacherDetail.status === "verified"
            }
            onClick={() => void handleModerationAction("verify")}
          >
            {actionPending === "verify" ? "Подтверждение..." : "Подтвердить"}
          </button>
          <button
            type="button"
            className="quick-filter"
            disabled={
              !teacherDetail ||
              actionPending !== null ||
              teacherDetail.status === "disabled"
            }
            onClick={() => void handleModerationAction("disable")}
          >
            {actionPending === "disable" ? "Отключение..." : "Отключить"}
          </button>
        </div>

        {detailLoading ? <p className="summary">Загрузка данных преподавателя...</p> : null}
        {detailError ? <p className="error-text">{detailError}</p> : null}
        {actionError ? <p className="error-text">{actionError}</p> : null}
        {actionSuccess ? <p className="success-text">{actionSuccess}</p> : null}

        {teacherDetail ? (
          <div className="teacher-detail">
            <p>
              <strong>Статус:</strong> {formatTeacherStatus(teacherDetail.status)}
            </p>
            <p>
              <strong>Подтверждён:</strong> {teacherDetail.verified ? "Да" : "Нет"}
            </p>
            <p>
              <strong>Активен:</strong> {teacherDetail.is_active ? "Да" : "Нет"}
            </p>
            <p>
              <strong>Опыт:</strong> {teacherDetail.experience_years} лет
            </p>
            <p>
              <strong>Почта:</strong> {teacherDetail.email}
            </p>
            <p>
              <strong>Теги:</strong> {teacherDetail.tags.length ? teacherDetail.tags.join(", ") : "нет"}
            </p>
            <p>
              <strong>О себе:</strong> {teacherDetail.bio}
            </p>
          </div>
        ) : (
          <p className="summary">Выберите преподавателя для просмотра карточки.</p>
        )}
      </article>
    </section>
  );
}
