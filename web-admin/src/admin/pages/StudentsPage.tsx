import { useEffect, useMemo, useRef, useState } from "react";

import { listAdminPackages } from "../../features/packages/api";
import type { AdminPackage } from "../../features/packages/types";
import { ApiClientError, apiClient } from "../../shared/api/client";
import type { PageResponse } from "../../shared/api/types";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);
const ADMIN_STUDENT_FILTER_STORAGE_KEY = "go_admin_students_selected_id";

type AdminStudentListItem = {
  user_id: string;
  email: string;
  full_name: string;
  timezone: string;
  role: "student";
  is_active: boolean;
  created_at_utc: string;
  updated_at_utc: string;
};

type StudentPackageSummary = {
  packagesTotal: number;
  activePackages: number;
  lessonsLeft: number;
  lessonsReserved: number;
};

function formatDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(parsed);
}

function summarizePackages(packages: AdminPackage[]): StudentPackageSummary {
  return packages.reduce<StudentPackageSummary>(
    (summary, pkg) => ({
      packagesTotal: summary.packagesTotal + 1,
      activePackages: summary.activePackages + (pkg.status === "active" ? 1 : 0),
      lessonsLeft: summary.lessonsLeft + pkg.lessons_left,
      lessonsReserved: summary.lessonsReserved + pkg.lessons_reserved
    }),
    {
      packagesTotal: 0,
      activePackages: 0,
      lessonsLeft: 0,
      lessonsReserved: 0
    }
  );
}

export function StudentsPage() {
  const [students, setStudents] = useState<AdminStudentListItem[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(
    () => localStorage.getItem(ADMIN_STUDENT_FILTER_STORAGE_KEY) || null
  );
  const selectedStudentRef = useRef<string | null>(selectedStudentId);

  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [packages, setPackages] = useState<AdminPackage[]>([]);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    selectedStudentRef.current = selectedStudentId;
  }, [selectedStudentId]);

  useEffect(() => {
    if (!selectedStudentId) {
      localStorage.removeItem(ADMIN_STUDENT_FILTER_STORAGE_KEY);
      return;
    }
    localStorage.setItem(ADMIN_STUDENT_FILTER_STORAGE_KEY, selectedStudentId);
  }, [selectedStudentId]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setUnavailable(false);

    apiClient
      .request<PageResponse<AdminStudentListItem>>(
        "/admin/users?role=student&limit=100&offset=0"
      )
      .then((page) => {
        if (!active) {
          return;
        }
        setStudents(page.items);
        const preferredStudentId = selectedStudentRef.current ?? page.items[0]?.user_id ?? null;
        const hasPreferred = page.items.some((item) => item.user_id === preferredStudentId);
        setSelectedStudentId(hasPreferred ? preferredStudentId : page.items[0]?.user_id ?? null);
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
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Не удалось загрузить список учеников"
        );
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedStudentId || unavailable) {
      setPackages([]);
      setDetailError(null);
      return;
    }

    let active = true;
    setDetailLoading(true);
    setDetailError(null);

    listAdminPackages({ studentId: selectedStudentId })
      .then((page) => {
        if (active) {
          setPackages(page.items);
        }
      })
      .catch((requestError) => {
        if (!active) {
          return;
        }
        setPackages([]);
        setDetailError(
          requestError instanceof Error
            ? requestError.message
            : "Не удалось загрузить пакеты ученика"
        );
      })
      .finally(() => {
        if (active) {
          setDetailLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [selectedStudentId, unavailable]);

  const selectedStudent = useMemo(
    () => students.find((item) => item.user_id === selectedStudentId) ?? null,
    [selectedStudentId, students]
  );
  const packageSummary = useMemo(() => summarizePackages(packages), [packages]);

  if (unavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Студенты</p>
        <h1>Эндпоинт недоступен</h1>
        <p className="summary">
          Для раздела нужны <code>GET /admin/users?role=student</code> и{" "}
          <code>GET /admin/packages</code>.
        </p>
      </article>
    );
  }

  if (loading) {
    return (
      <article className="card section-page">
        <h1>Студенты</h1>
        <p className="summary">Загрузка списка учеников...</p>
      </article>
    );
  }

  if (error) {
    return (
      <article className="card section-page">
        <h1>Студенты</h1>
        <p className="error-text">{error}</p>
      </article>
    );
  }

  return (
    <section className="teachers-grid">
      <article className="card">
        <p className="eyebrow">Студенты</p>
        <h1>Список учеников</h1>
        {students.length === 0 ? (
          <p className="summary">Пока нет учеников.</p>
        ) : (
          <div className="teacher-list">
            {students.map((student) => (
              <button
                key={student.user_id}
                type="button"
                className={
                  student.user_id === selectedStudentId ? "teacher-item active" : "teacher-item"
                }
                onClick={() => setSelectedStudentId(student.user_id)}
              >
                <strong>{student.full_name}</strong>
                <span>{student.email}</span>
                <span>{student.timezone}</span>
                <span>{student.is_active ? "активен" : "отключён"}</span>
              </button>
            ))}
          </div>
        )}
      </article>

      <article className="card">
        <p className="eyebrow">Карточка ученика</p>
        {selectedStudent ? <h1>{selectedStudent.full_name}</h1> : <h1>Не выбрано</h1>}

        {detailLoading ? <p className="summary">Загрузка карточки ученика...</p> : null}
        {detailError ? <p className="error-text">{detailError}</p> : null}

        {selectedStudent ? (
          <div className="teacher-detail">
            <p>
              <strong>ФИО:</strong> {selectedStudent.full_name}
            </p>
            <p>
              <strong>Почта:</strong> {selectedStudent.email}
            </p>
            <p>
              <strong>Таймзона:</strong> {selectedStudent.timezone}
            </p>
            <p>
              <strong>Активен:</strong> {selectedStudent.is_active ? "Да" : "Нет"}
            </p>
            <p>
              <strong>Создан:</strong> {formatDateTime(selectedStudent.created_at_utc)}
            </p>
            <p>
              <strong>Обновлён:</strong> {formatDateTime(selectedStudent.updated_at_utc)}
            </p>
          </div>
        ) : (
          <p className="summary">Выберите ученика для просмотра карточки.</p>
        )}

        <section className="teacher-schedule-block">
          <h2>Пакеты ученика</h2>
          <div className="users-metrics-grid">
            <div className="kpi-tile">
              <h3>Всего пакетов</h3>
              <p>{packageSummary.packagesTotal}</p>
            </div>
            <div className="kpi-tile">
              <h3>Активных</h3>
              <p>{packageSummary.activePackages}</p>
            </div>
            <div className="kpi-tile">
              <h3>Уроков осталось</h3>
              <p>{packageSummary.lessonsLeft}</p>
            </div>
            <div className="kpi-tile">
              <h3>Зарезервировано</h3>
              <p>{packageSummary.lessonsReserved}</p>
            </div>
          </div>
        </section>
      </article>
    </section>
  );
}
