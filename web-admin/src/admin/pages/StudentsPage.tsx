import { useEffect, useMemo, useState } from "react";

import { ApiClientError } from "../../shared/api/client";
import { listAdminPackages } from "../../features/packages/api";
import type { AdminPackage } from "../../features/packages/types";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);

type StudentRow = {
  studentId: string;
  packagesTotal: number;
  activePackages: number;
  lessonsLeft: number;
  lessonsReserved: number;
};

export function StudentsPage() {
  const [packages, setPackages] = useState<AdminPackage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    listAdminPackages()
      .then((page) => {
        setPackages(page.items);
      })
      .catch((requestError) => {
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
            : "Не удалось загрузить данные по пакетам студентов"
        );
      })
      .finally(() => setLoading(false));
  }, []);

  const rows = useMemo<StudentRow[]>(() => {
    const byStudent = new Map<string, StudentRow>();
    for (const pkg of packages) {
      const current = byStudent.get(pkg.student_id) ?? {
        studentId: pkg.student_id,
        packagesTotal: 0,
        activePackages: 0,
        lessonsLeft: 0,
        lessonsReserved: 0
      };
      current.packagesTotal += 1;
      if (pkg.status === "active") {
        current.activePackages += 1;
      }
      current.lessonsLeft += pkg.lessons_left;
      current.lessonsReserved += pkg.lessons_reserved;
      byStudent.set(pkg.student_id, current);
    }
    return Array.from(byStudent.values()).sort((a, b) => b.packagesTotal - a.packagesTotal);
  }, [packages]);

  if (unavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Студенты</p>
        <h1>Эндпоинт недоступен</h1>
        <p className="summary">
          Для сводки по пакетам студентов требуется <code>GET /admin/packages</code>.
        </p>
      </article>
    );
  }

  if (loading) {
    return (
      <article className="card section-page">
        <h1>Студенты</h1>
        <p className="summary">Загрузка сводки по студентам...</p>
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
    <article className="card section-page">
      <p className="eyebrow">Студенты</p>
      <h1>Сводка пакетов студентов</h1>
      {rows.length ? (
        <div className="bookings-table-wrap">
          <table className="bookings-table">
            <thead>
              <tr>
                <th>ID студента</th>
                <th>Пакетов</th>
                <th>Активных</th>
                <th>Уроков осталось</th>
                <th>Зарезервировано</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.studentId}>
                  <td>{row.studentId}</td>
                  <td>{row.packagesTotal}</td>
                  <td>{row.activePackages}</td>
                  <td>{row.lessonsLeft}</td>
                  <td>{row.lessonsReserved}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="summary">Пока нет данных по пакетам студентов.</p>
      )}
    </article>
  );
}
