import { useEffect, useMemo, useRef, useState } from "react";

import { listAdminBookings } from "../../features/bookings/api";
import type { AdminBooking } from "../../features/bookings/types";
import { listAdminPackages } from "../../features/packages/api";
import type { AdminPackage } from "../../features/packages/types";
import { listTeachers } from "../../features/teachers/api";
import type { TeacherListItem } from "../../features/teachers/types";
import { ApiClientError, apiClient } from "../../shared/api/client";
import type { PageResponse } from "../../shared/api/types";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);
const ADMIN_STUDENT_FILTER_STORAGE_KEY = "go_admin_students_selected_id";
const ACTIVE_BOOKING_STATUSES = new Set<AdminBooking["status"]>(["hold", "confirmed"]);

const PACKAGE_STATUS_LABELS: Record<AdminPackage["status"], string> = {
  active: "активен",
  expired: "истёк",
  depleted: "исчерпан",
  canceled: "отменён"
};

const BOOKING_STATUS_LABELS: Record<AdminBooking["status"], string> = {
  hold: "удержание",
  confirmed: "подтверждено",
  canceled: "отменено",
  expired: "истекло"
};

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

type StudentTeacherSummary = {
  teacherId: string;
  bookingsTotal: number;
  lastLessonUtc: string | null;
};

type StudentPreferredTimeSummary = {
  weekday: string;
  startTime: string;
  endTime: string;
  count: number;
  nextAtUtc: string | null;
};

type StudentActiveFilter = "all" | "active" | "inactive";

function formatDateTime(value: string, timezone?: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
    ...(timezone ? { timeZone: timezone } : {})
  }).format(parsed);
}

function formatTime(value: string, timezone: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: timezone
  }).format(parsed);
}

function formatWeekday(value: string, timezone: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat("ru-RU", {
    weekday: "long",
    timeZone: timezone
  }).format(parsed);
}

function formatPackageStatus(status: AdminPackage["status"]): string {
  return PACKAGE_STATUS_LABELS[status] ?? status;
}

function formatBookingStatus(status: AdminBooking["status"]): string {
  return BOOKING_STATUS_LABELS[status] ?? status;
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
  const [activeFilter, setActiveFilter] = useState<StudentActiveFilter>("all");
  const [query, setQuery] = useState("");

  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [teachersLoading, setTeachersLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [bookingsError, setBookingsError] = useState<string | null>(null);
  const [teachersError, setTeachersError] = useState<string | null>(null);

  const [packages, setPackages] = useState<AdminPackage[]>([]);
  const [bookings, setBookings] = useState<AdminBooking[]>([]);
  const [teachers, setTeachers] = useState<TeacherListItem[]>([]);

  const [unavailable, setUnavailable] = useState(false);
  const [bookingsUnavailable, setBookingsUnavailable] = useState(false);
  const [teachersUnavailable, setTeachersUnavailable] = useState(false);

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
    let active = true;
    setTeachersLoading(true);
    setTeachersError(null);
    setTeachersUnavailable(false);

    listTeachers()
      .then((page) => {
        if (active) {
          setTeachers(page.items);
        }
      })
      .catch((requestError) => {
        if (!active) {
          return;
        }
        if (
          requestError instanceof ApiClientError &&
          UNAVAILABLE_STATUSES.has(requestError.status)
        ) {
          setTeachersUnavailable(true);
          setTeachers([]);
          return;
        }
        setTeachersError(
          requestError instanceof Error
            ? requestError.message
            : "Не удалось загрузить список преподавателей"
        );
      })
      .finally(() => {
        if (active) {
          setTeachersLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedStudentId || unavailable) {
      setPackages([]);
      setBookings([]);
      setDetailError(null);
      setBookingsError(null);
      setBookingsUnavailable(false);
      return;
    }

    let active = true;
    setDetailLoading(true);
    setDetailError(null);
    setBookingsError(null);
    setBookingsUnavailable(false);

    Promise.allSettled([
      listAdminPackages({ studentId: selectedStudentId }),
      listAdminBookings({
        studentId: selectedStudentId,
        limit: 300,
        offset: 0
      })
    ])
      .then((results) => {
        if (!active) {
          return;
        }

        const packagesResult = results[0];
        if (packagesResult.status === "fulfilled") {
          setPackages(packagesResult.value.items);
        } else {
          setPackages([]);
          const packageError = packagesResult.reason;
          setDetailError(
            packageError instanceof Error
              ? packageError.message
              : "Не удалось загрузить пакеты ученика"
          );
        }

        const bookingsResult = results[1];
        if (bookingsResult.status === "fulfilled") {
          setBookings(bookingsResult.value.items);
        } else {
          setBookings([]);
          const bookingError = bookingsResult.reason;
          if (
            bookingError instanceof ApiClientError &&
            UNAVAILABLE_STATUSES.has(bookingError.status)
          ) {
            setBookingsUnavailable(true);
          } else {
            setBookingsError(
              bookingError instanceof Error
                ? bookingError.message
                : "Не удалось загрузить бронирования ученика"
            );
          }
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
  }, [selectedStudentId, unavailable]);

  const selectedStudent = useMemo(
    () => students.find((item) => item.user_id === selectedStudentId) ?? null,
    [selectedStudentId, students]
  );
  const packageSummary = useMemo(() => summarizePackages(packages), [packages]);
  const filteredStudents = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return students.filter((student) => {
      const matchesStatus =
        activeFilter === "all" ||
        (activeFilter === "active" ? student.is_active : !student.is_active);

      if (!matchesStatus) {
        return false;
      }

      if (!normalizedQuery) {
        return true;
      }

      return (
        student.full_name.toLowerCase().includes(normalizedQuery) ||
        student.email.toLowerCase().includes(normalizedQuery) ||
        student.user_id.toLowerCase().includes(normalizedQuery)
      );
    });
  }, [activeFilter, query, students]);

  useEffect(() => {
    if (filteredStudents.length === 0) {
      setSelectedStudentId(null);
      return;
    }
    if (selectedStudentId && filteredStudents.some((item) => item.user_id === selectedStudentId)) {
      return;
    }
    setSelectedStudentId(filteredStudents[0].user_id);
  }, [filteredStudents, selectedStudentId]);

  const teacherById = useMemo(
    () => new Map(teachers.map((teacher) => [teacher.teacher_id, teacher])),
    [teachers]
  );

  const teacherSummaries = useMemo<StudentTeacherSummary[]>(() => {
    const byTeacher = new Map<string, StudentTeacherSummary>();

    for (const booking of bookings) {
      if (!ACTIVE_BOOKING_STATUSES.has(booking.status)) {
        continue;
      }

      const existing = byTeacher.get(booking.teacher_id) ?? {
        teacherId: booking.teacher_id,
        bookingsTotal: 0,
        lastLessonUtc: null
      };
      existing.bookingsTotal += 1;

      if (
        existing.lastLessonUtc === null ||
        new Date(booking.slot_start_at_utc).getTime() > new Date(existing.lastLessonUtc).getTime()
      ) {
        existing.lastLessonUtc = booking.slot_start_at_utc;
      }

      byTeacher.set(booking.teacher_id, existing);
    }

    return [...byTeacher.values()].sort((left, right) => {
      if (left.bookingsTotal !== right.bookingsTotal) {
        return right.bookingsTotal - left.bookingsTotal;
      }
      if (!left.lastLessonUtc) {
        return 1;
      }
      if (!right.lastLessonUtc) {
        return -1;
      }
      return new Date(right.lastLessonUtc).getTime() - new Date(left.lastLessonUtc).getTime();
    });
  }, [bookings]);

  const preferredTimeSummaries = useMemo<StudentPreferredTimeSummary[]>(() => {
    const timezone = selectedStudent?.timezone || "UTC";
    const byTime = new Map<string, StudentPreferredTimeSummary>();
    const now = Date.now();

    for (const booking of bookings) {
      if (!ACTIVE_BOOKING_STATUSES.has(booking.status)) {
        continue;
      }

      const start = new Date(booking.slot_start_at_utc);
      const end = new Date(booking.slot_end_at_utc);
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
        continue;
      }

      const weekday = formatWeekday(booking.slot_start_at_utc, timezone);
      const startTime = formatTime(booking.slot_start_at_utc, timezone);
      const endTime = formatTime(booking.slot_end_at_utc, timezone);
      const key = `${weekday}-${startTime}-${endTime}`;

      const existing = byTime.get(key) ?? {
        weekday,
        startTime,
        endTime,
        count: 0,
        nextAtUtc: null
      };
      existing.count += 1;

      if (start.getTime() >= now) {
        if (
          existing.nextAtUtc === null ||
          start.getTime() < new Date(existing.nextAtUtc).getTime()
        ) {
          existing.nextAtUtc = booking.slot_start_at_utc;
        }
      }

      byTime.set(key, existing);
    }

    return [...byTime.values()]
      .sort((left, right) => {
        if (left.count !== right.count) {
          return right.count - left.count;
        }
        if (!left.nextAtUtc && !right.nextAtUtc) {
          return 0;
        }
        if (!left.nextAtUtc) {
          return 1;
        }
        if (!right.nextAtUtc) {
          return -1;
        }
        return new Date(left.nextAtUtc).getTime() - new Date(right.nextAtUtc).getTime();
      })
      .slice(0, 6);
  }, [bookings, selectedStudent?.timezone]);

  const upcomingBookings = useMemo(() => {
    const now = Date.now();
    return bookings
      .filter(
        (booking) =>
          ACTIVE_BOOKING_STATUSES.has(booking.status) &&
          new Date(booking.slot_start_at_utc).getTime() >= now
      )
      .sort(
        (left, right) =>
          new Date(left.slot_start_at_utc).getTime() - new Date(right.slot_start_at_utc).getTime()
      )
      .slice(0, 5);
  }, [bookings]);

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
    <section className="teachers-grid students-grid">
      <article className="card students-card">
        <p className="eyebrow">Студенты</p>
        <h1>Список учеников</h1>
        <div className="users-provision-form students-filter-form">
          <label>
            <span>Статус</span>
            <select
              value={activeFilter}
              onChange={(event) => setActiveFilter(event.target.value as StudentActiveFilter)}
            >
              <option value="all">Все</option>
              <option value="active">Только активные</option>
              <option value="inactive">Только отключённые</option>
            </select>
          </label>

          <label>
            <span>Поиск (ФИО / почта / ID)</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="например, student@... или Иванов"
            />
          </label>
        </div>

        <p className="summary">Найдено учеников: {filteredStudents.length}</p>

        {students.length === 0 ? (
          <p className="summary">Пока нет учеников в системе.</p>
        ) : filteredStudents.length === 0 ? (
          <p className="summary">По выбранным фильтрам ученики не найдены.</p>
        ) : (
          <div className="teacher-list students-list">
            {filteredStudents.map((student) => (
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
        {bookingsError ? <p className="error-text">{bookingsError}</p> : null}
        {teachersError ? <p className="error-text">{teachersError}</p> : null}

        {selectedStudent ? (
          <div className="teacher-detail students-detail">
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
          <div className="users-metrics-grid students-metrics-grid">
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

          {packages.length ? (
            <div className="bookings-table-wrap">
              <table className="bookings-table students-packages-table">
                <thead>
                  <tr>
                    <th>Пакет</th>
                    <th>Статус</th>
                    <th>Осталось</th>
                    <th>Зарезервировано</th>
                    <th>Стоимость</th>
                    <th>Истекает</th>
                  </tr>
                </thead>
                <tbody>
                  {packages.map((pkg) => (
                    <tr key={pkg.package_id}>
                      <td>{pkg.package_id.slice(0, 8)}</td>
                      <td>{formatPackageStatus(pkg.status)}</td>
                      <td>{pkg.lessons_left}</td>
                      <td>{pkg.lessons_reserved}</td>
                      <td>
                        {pkg.price_amount
                          ? `${pkg.price_amount} ${pkg.price_currency ?? ""}`
                          : "-"}
                      </td>
                      <td>{formatDateTime(pkg.expires_at_utc)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="summary">У ученика пока нет пакетов.</p>
          )}
        </section>

        <section className="teacher-schedule-block">
          <h2>Преподаватели ученика</h2>
          {teachersLoading ? <p className="summary">Загрузка преподавателей...</p> : null}
          {teachersUnavailable ? (
            <p className="summary">`GET /admin/teachers` недоступен в текущем backend-контракте.</p>
          ) : null}
          {!teachersLoading && !teachersUnavailable ? (
            teacherSummaries.length ? (
              <div className="users-teachers-list students-teachers-list">
                {teacherSummaries.map((item) => {
                  const teacher = teacherById.get(item.teacherId);
                  return (
                    <article key={item.teacherId} className="users-teacher-item">
                      <p>
                        <strong>{teacher?.display_name ?? item.teacherId}</strong>
                      </p>
                      <p>{teacher?.full_name ?? "Данные профиля недоступны"}</p>
                      <p>{teacher?.email ?? "-"}</p>
                      <p>Уроков с учеником: {item.bookingsTotal}</p>
                      <p>
                        Последний слот: {item.lastLessonUtc ? formatDateTime(item.lastLessonUtc) : "-"}
                      </p>
                    </article>
                  );
                })}
              </div>
            ) : (
              <p className="summary">У ученика пока нет активных бронирований с преподавателями.</p>
            )
          ) : null}
        </section>

        <section className="teacher-schedule-block">
          <h2>Выбранное время для занятий</h2>
          <p className="summary">
            Локальная зона ученика: <code>{selectedStudent?.timezone ?? "UTC"}</code>
          </p>
          {bookingsUnavailable ? (
            <p className="summary">`GET /admin/bookings` недоступен в текущем backend-контракте.</p>
          ) : preferredTimeSummaries.length ? (
            <div className="bookings-table-wrap">
              <table className="bookings-table students-time-table">
                <thead>
                  <tr>
                    <th>День недели</th>
                    <th>Время</th>
                    <th>Выборов</th>
                    <th>Ближайшее занятие</th>
                  </tr>
                </thead>
                <tbody>
                  {preferredTimeSummaries.map((item) => (
                    <tr key={`${item.weekday}-${item.startTime}-${item.endTime}`}>
                      <td>{item.weekday}</td>
                      <td>
                        {item.startTime} - {item.endTime}
                      </td>
                      <td>{item.count}</td>
                      <td>
                        {item.nextAtUtc
                          ? formatDateTime(item.nextAtUtc, selectedStudent?.timezone)
                          : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="summary">Пока нет подтверждённых или удерживаемых бронирований.</p>
          )}

          {upcomingBookings.length ? (
            <div className="bookings-table-wrap">
              <table className="bookings-table students-upcoming-table">
                <thead>
                  <tr>
                    <th>Ближайшие занятия</th>
                    <th>Преподаватель</th>
                    <th>Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {upcomingBookings.map((booking) => {
                    const teacher = teacherById.get(booking.teacher_id);
                    return (
                      <tr key={booking.booking_id}>
                        <td>
                          {formatWeekday(booking.slot_start_at_utc, selectedStudent?.timezone ?? "UTC")} {" "}
                          {formatTime(booking.slot_start_at_utc, selectedStudent?.timezone ?? "UTC")} -{" "}
                          {formatTime(booking.slot_end_at_utc, selectedStudent?.timezone ?? "UTC")}
                        </td>
                        <td>{teacher?.display_name ?? booking.teacher_id}</td>
                        <td>{formatBookingStatus(booking.status)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      </article>
    </section>
  );
}
