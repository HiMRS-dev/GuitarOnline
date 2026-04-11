import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiClientError, apiClient } from "../../shared/api/client";
import type { PageResponse } from "../../shared/api/types";
import {
  cancelAdminPackage,
  createAdminPackage,
  listAdminPackages
} from "../../features/packages/api";
import type { AdminPackage } from "../../features/packages/types";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const PACKAGE_STATUSES = ["", "active", "expired", "depleted", "canceled"];
const PACKAGE_STATUS_LABELS: Record<string, string> = {
  active: "активен",
  expired: "истёк",
  depleted: "исчерпан",
  canceled: "отменён"
};

type AdminStudentLookupItem = {
  user_id: string;
  email: string;
  full_name: string;
  role: "student";
  is_active: boolean;
  created_at_utc: string;
  updated_at_utc: string;
};

function formatPackageStatus(status: string): string {
  return PACKAGE_STATUS_LABELS[status] ?? status;
}

function resolveStudentId(
  value: string,
  students: AdminStudentLookupItem[]
): { studentId: string | null; ambiguous: boolean } {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return { studentId: null, ambiguous: false };
  }

  const exact = students.filter((student) => {
    return (
      student.user_id.toLowerCase() === normalized ||
      student.email.toLowerCase() === normalized ||
      student.full_name.toLowerCase() === normalized
    );
  });
  if (exact.length === 1) {
    return { studentId: exact[0].user_id, ambiguous: false };
  }
  if (exact.length > 1) {
    return { studentId: null, ambiguous: true };
  }

  if (students.length === 1) {
    return { studentId: students[0].user_id, ambiguous: false };
  }
  if (students.length > 1) {
    return { studentId: null, ambiguous: true };
  }

  return { studentId: null, ambiguous: false };
}

export function PackagesPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const [packages, setPackages] = useState<AdminPackage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);
  const [createPending, setCreatePending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [cancelPendingPackageId, setCancelPendingPackageId] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  const [studentInput, setStudentInput] = useState("");
  const [selectedStudent, setSelectedStudent] = useState<AdminStudentLookupItem | null>(null);
  const [studentSuggestions, setStudentSuggestions] = useState<AdminStudentLookupItem[]>([]);
  const [studentsLookupLoading, setStudentsLookupLoading] = useState(false);
  const [studentsLookupUnavailable, setStudentsLookupUnavailable] = useState(false);
  const [studentsLookupError, setStudentsLookupError] = useState<string | null>(null);
  const [lessonsTotal, setLessonsTotal] = useState("8");
  const [expiresAtUtc, setExpiresAtUtc] = useState("");
  const [priceAmount, setPriceAmount] = useState("149.00");
  const [priceCurrency, setPriceCurrency] = useState("USD");

  const studentLookupRequestIdRef = useRef(0);

  const loadPackages = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await listAdminPackages({
        status: statusFilter || undefined
      });
      setPackages(page.items);
    } catch (requestError) {
      if (requestError instanceof ApiClientError && UNAVAILABLE_STATUSES.has(requestError.status)) {
        setUnavailable(true);
        return;
      }
      setError(requestError instanceof Error ? requestError.message : "Не удалось загрузить пакеты");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  const searchStudents = useCallback(
    async (query: string): Promise<AdminStudentLookupItem[]> => {
      const requestId = ++studentLookupRequestIdRef.current;
      setStudentsLookupLoading(true);
      setStudentsLookupError(null);
      setStudentsLookupUnavailable(false);

      try {
        const params = new URLSearchParams({
          role: "student",
          limit: "20",
          offset: "0",
          q: query
        });
        const page = await apiClient.request<PageResponse<AdminStudentLookupItem>>(
          `/admin/users?${params.toString()}`
        );

        if (requestId === studentLookupRequestIdRef.current) {
          setStudentSuggestions(page.items);
        }
        return page.items;
      } catch (requestError) {
        if (requestError instanceof ApiClientError && UNAVAILABLE_STATUSES.has(requestError.status)) {
          if (requestId === studentLookupRequestIdRef.current) {
            setStudentsLookupUnavailable(true);
            setStudentSuggestions([]);
          }
          return [];
        }
        if (requestId === studentLookupRequestIdRef.current) {
          setStudentsLookupError(
            requestError instanceof Error
              ? requestError.message
              : "Не удалось загрузить список студентов"
          );
          setStudentSuggestions([]);
        }
        return [];
      } finally {
        if (requestId === studentLookupRequestIdRef.current) {
          setStudentsLookupLoading(false);
        }
      }
    },
    []
  );

  useEffect(() => {
    void loadPackages();
  }, [loadPackages]);

  useEffect(() => {
    const normalizedInput = studentInput.trim();
    if (!normalizedInput || UUID_PATTERN.test(normalizedInput)) {
      setStudentSuggestions([]);
      setStudentsLookupError(null);
      setStudentsLookupLoading(false);
      return;
    }

    const timeoutId = window.setTimeout(() => {
      void searchStudents(normalizedInput);
    }, 250);

    return () => window.clearTimeout(timeoutId);
  }, [searchStudents, studentInput]);

  const showStudentSuggestions = useMemo(() => {
    const normalized = studentInput.trim();
    return normalized.length > 0 && !UUID_PATTERN.test(normalized);
  }, [studentInput]);

  async function handleCreatePackage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    setCreateSuccess(null);

    const normalizedStudentInput = studentInput.trim();
    const parsedLessonsTotal = Number(lessonsTotal);
    const parsedExpiresAt = new Date(expiresAtUtc);

    if (!normalizedStudentInput) {
      setCreateError("ID или ФИО студента обязательны.");
      return;
    }
    if (!Number.isInteger(parsedLessonsTotal) || parsedLessonsTotal <= 0) {
      setCreateError("Количество уроков должно быть положительным целым числом.");
      return;
    }
    if (!expiresAtUtc || Number.isNaN(parsedExpiresAt.getTime())) {
      setCreateError("Дата истечения (UTC) обязательна.");
      return;
    }
    if (!priceAmount.trim()) {
      setCreateError("Стоимость обязательна.");
      return;
    }

    let resolvedStudentId = selectedStudent?.user_id ?? null;
    if (!resolvedStudentId) {
      if (UUID_PATTERN.test(normalizedStudentInput)) {
        resolvedStudentId = normalizedStudentInput;
      } else {
        const students = await searchStudents(normalizedStudentInput);
        if (studentsLookupUnavailable) {
          setCreateError("Поиск по ФИО недоступен. Укажите `student_id` вручную.");
          return;
        }
        if (studentsLookupError && students.length === 0) {
          setCreateError("Не удалось выполнить поиск студента. Укажите `student_id` вручную.");
          return;
        }

        const resolved = resolveStudentId(normalizedStudentInput, students);
        if (resolved.ambiguous) {
          setCreateError("Найдено несколько студентов. Уточните ФИО или выберите из подсказок.");
          return;
        }
        if (!resolved.studentId) {
          setCreateError("Студент не найден. Укажите `student_id` или выберите подсказку.");
          return;
        }
        resolvedStudentId = resolved.studentId;
      }
    }

    setCreatePending(true);
    try {
      const createdPackage = await createAdminPackage({
        student_id: resolvedStudentId,
        lessons_total: parsedLessonsTotal,
        expires_at_utc: parsedExpiresAt.toISOString(),
        price_amount: priceAmount.trim(),
        price_currency: (priceCurrency.trim() || "USD").toUpperCase()
      });
      setCreateSuccess(`Пакет создан: ${createdPackage.package_id}`);
      await loadPackages();
    } catch (requestError) {
      setCreateError(requestError instanceof Error ? requestError.message : "Не удалось создать пакет");
    } finally {
      setCreatePending(false);
    }
  }

  async function handleCancelPackage(pkg: AdminPackage) {
    if (pkg.status === "canceled") {
      return;
    }

    const shouldCancel = window.confirm(
      `Удалить пакет ${pkg.package_id.slice(0, 8)}? Пакет будет переведен в статус "отменен".`
    );
    if (!shouldCancel) {
      return;
    }

    setActionError(null);
    setActionSuccess(null);
    setCancelPendingPackageId(pkg.package_id);
    try {
      const canceledPackage = await cancelAdminPackage(pkg.package_id);
      setActionSuccess(`Пакет удален: ${canceledPackage.package_id}`);
      await loadPackages();
    } catch (requestError) {
      setActionError(requestError instanceof Error ? requestError.message : "Не удалось удалить пакет");
    } finally {
      setCancelPendingPackageId(null);
    }
  }

  if (unavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Пакеты</p>
        <h1>Эндпоинт недоступен</h1>
        <p className="summary">
          Для управления пакетами требуются <code>GET /admin/packages</code> и
          <code>POST /admin/packages</code>, <code>POST /admin/packages/{`{id}`}/cancel</code>.
        </p>
      </article>
    );
  }

  return (
    <article className="card section-page">
      <p className="eyebrow">Пакеты</p>
      <h1>Пакеты</h1>

      <form className="users-provision-form" onSubmit={handleCreatePackage}>
        <h2>Создать пакет</h2>
        <label className="teachers-picker-search">
          <span>Студент (ID или ФИО)</span>
          <input
            type="text"
            value={studentInput}
            onChange={(event) => {
              setStudentInput(event.target.value);
              setSelectedStudent(null);
            }}
            placeholder="UUID student_id, ФИО или email"
          />
        </label>
        {showStudentSuggestions ? (
          <div className="picker-search-suggestions">
            {studentsLookupLoading ? <p className="summary">Загружаем подсказки...</p> : null}
            {!studentsLookupLoading && !studentsLookupUnavailable && studentSuggestions.length ? (
              <div className="picker-suggestion-list">
                {studentSuggestions.map((student) => (
                  <div key={student.user_id} className="picker-suggestion-item">
                    <div className="picker-suggestion-meta">
                      <strong>{student.full_name}</strong>
                      <span>{student.email}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedStudent(student);
                        setStudentInput(student.full_name);
                        setStudentSuggestions([]);
                      }}
                    >
                      Выбрать
                    </button>
                  </div>
                ))}
              </div>
            ) : null}
            {!studentsLookupLoading &&
            !studentsLookupUnavailable &&
            !studentsLookupError &&
            studentSuggestions.length === 0 ? (
              <p className="summary">Совпадений не найдено.</p>
            ) : null}
          </div>
        ) : null}
        {selectedStudent ? (
          <p className="summary">
            Выбран студент: <strong>{selectedStudent.full_name}</strong> (
            <code>{selectedStudent.user_id}</code>)
          </p>
        ) : null}
        {studentsLookupUnavailable ? (
          <p className="summary">Поиск по ФИО недоступен. Можно создать пакет только по `student_id`.</p>
        ) : null}
        {studentsLookupError ? <p className="error-text">{studentsLookupError}</p> : null}

        <label>
          <span>Количество уроков</span>
          <input
            type="number"
            min={1}
            value={lessonsTotal}
            onChange={(event) => setLessonsTotal(event.target.value)}
          />
        </label>
        <label>
          <span>Истекает в (UTC)</span>
          <input
            type="datetime-local"
            value={expiresAtUtc}
            onChange={(event) => setExpiresAtUtc(event.target.value)}
          />
        </label>
        <label>
          <span>Стоимость</span>
          <input
            type="text"
            value={priceAmount}
            onChange={(event) => setPriceAmount(event.target.value)}
            placeholder="149.00"
          />
        </label>
        <label>
          <span>Валюта</span>
          <input
            type="text"
            value={priceCurrency}
            onChange={(event) => setPriceCurrency(event.target.value)}
            placeholder="USD"
            maxLength={3}
          />
        </label>
        <button type="submit" disabled={createPending}>
          {createPending ? "Создание..." : "Создать пакет"}
        </button>
        {createError ? <p className="error-text">{createError}</p> : null}
        {createSuccess ? <p className="success-text">{createSuccess}</p> : null}
      </form>

      <label className="inline-filter">
        <span>Статус</span>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          {PACKAGE_STATUSES.map((status) => (
            <option key={status || "all"} value={status}>
              {status ? formatPackageStatus(status) : "все"}
            </option>
          ))}
        </select>
      </label>

      {loading ? <p className="summary">Загрузка пакетов...</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {actionError ? <p className="error-text">{actionError}</p> : null}
      {actionSuccess ? <p className="success-text">{actionSuccess}</p> : null}

      {!loading && !error ? (
        packages.length ? (
          <div className="bookings-table-wrap">
            <table className="bookings-table">
              <thead>
                <tr>
                  <th>Действие</th>
                  <th>Пакет</th>
                  <th>Студент</th>
                  <th>Статус</th>
                  <th>Осталось</th>
                  <th>Зарезервировано</th>
                  <th>Цена</th>
                  <th>Истекает</th>
                </tr>
              </thead>
              <tbody>
                {packages.map((pkg) => {
                  const isPending = cancelPendingPackageId === pkg.package_id;
                  const isCanceled = pkg.status === "canceled";
                  const hasReservedLessons = pkg.lessons_reserved > 0;
                  const cancelDisabled = isPending || isCanceled || hasReservedLessons;

                  return (
                    <tr key={pkg.package_id}>
                      <td>
                        <button
                          type="button"
                          className="quick-filter"
                          onClick={() => void handleCancelPackage(pkg)}
                          disabled={cancelDisabled}
                          title={
                            hasReservedLessons
                              ? "Нельзя удалить пакет с зарезервированными уроками."
                              : undefined
                          }
                        >
                          {isPending ? "Удаляем..." : isCanceled ? "Удален" : "Удалить"}
                        </button>
                      </td>
                      <td>{pkg.package_id.slice(0, 8)}</td>
                      <td>{pkg.student_id.slice(0, 8)}</td>
                      <td>{formatPackageStatus(pkg.status)}</td>
                      <td>{pkg.lessons_left}</td>
                      <td>{pkg.lessons_reserved}</td>
                      <td>{pkg.price_amount ? `${pkg.price_amount} ${pkg.price_currency ?? ""}` : "-"}</td>
                      <td>{new Date(pkg.expires_at_utc).toISOString()}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="summary">По выбранному фильтру пакеты не найдены.</p>
        )
      ) : null}
    </article>
  );
}
