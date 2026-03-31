import { useCallback, useEffect, useMemo, useState } from "react";

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
const ADMIN_STUDENT_PROFILE_STORAGE_KEY = "go_admin_students_selected_profile";
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

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function loadStoredSelectedStudent(): AdminStudentListItem | null {
  if (!canUseStorage()) {
    return null;
  }

  const raw = window.localStorage.getItem(ADMIN_STUDENT_PROFILE_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as Partial<AdminStudentListItem>;
    if (
      typeof parsed.user_id !== "string" ||
      typeof parsed.email !== "string" ||
      typeof parsed.full_name !== "string" ||
      typeof parsed.timezone !== "string" ||
      typeof parsed.is_active !== "boolean" ||
      typeof parsed.created_at_utc !== "string" ||
      typeof parsed.updated_at_utc !== "string"
    ) {
      window.localStorage.removeItem(ADMIN_STUDENT_PROFILE_STORAGE_KEY);
      return null;
    }

    return {
      user_id: parsed.user_id,
      email: parsed.email,
      full_name: parsed.full_name,
      timezone: parsed.timezone,
      role: "student",
      is_active: parsed.is_active,
      created_at_utc: parsed.created_at_utc,
      updated_at_utc: parsed.updated_at_utc
    };
  } catch {
    window.localStorage.removeItem(ADMIN_STUDENT_PROFILE_STORAGE_KEY);
    return null;
  }
}

function persistSelectedStudent(profile: AdminStudentListItem | null): void {
  if (!canUseStorage()) {
    return;
  }

  if (!profile) {
    window.localStorage.removeItem(ADMIN_STUDENT_PROFILE_STORAGE_KEY);
    return;
  }

  window.localStorage.setItem(ADMIN_STUDENT_PROFILE_STORAGE_KEY, JSON.stringify(profile));
}

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
  const [selectedStudentProfile, setSelectedStudentProfile] = useState<AdminStudentListItem | null>(
    () => loadStoredSelectedStudent()
  );

  const [activeFilter, setActiveFilter] = useState<StudentActiveFilter>("all");
  const [query, setQuery] = useState("");
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const [studentsLoading, setStudentsLoading] = useState(false);
  const [studentsError, setStudentsError] = useState<string | null>(null);
  const [studentsUnavailable, setStudentsUnavailable] = useState(false);

  const [detailLoading, setDetailLoading] = useState(false);
  const [teachersLoading, setTeachersLoading] = useState(false);

  const [detailError, setDetailError] = useState<string | null>(null);
  const [bookingsError, setBookingsError] = useState<string | null>(null);
  const [teachersError, setTeachersError] = useState<string | null>(null);

  const [packages, setPackages] = useState<AdminPackage[]>([]);
  const [bookings, setBookings] = useState<AdminBooking[]>([]);
  const [teachers, setTeachers] = useState<TeacherListItem[]>([]);

  const [bookingsUnavailable, setBookingsUnavailable] = useState(false);
  const [teachersUnavailable, setTeachersUnavailable] = useState(false);

  const loadStudentsForPicker = useCallback(async () => {
    setStudentsLoading(true);
    setStudentsError(null);
    setStudentsUnavailable(false);

    try {
      const items: AdminStudentListItem[] = [];
      let offset = 0;
      const limit = 200;

      while (true) {
        const page = await apiClient.request<PageResponse<AdminStudentListItem>>(
          `/admin/users?role=student&limit=${limit}&offset=${offset}`
        );
        items.push(...page.items);
        offset += page.items.length;

        if (page.items.length < limit || items.length >= page.total) {
          break;
        }
      }

      setStudents(items);
    } catch (requestError) {
      if (
        requestError instanceof ApiClientError &&
        UNAVAILABLE_STATUSES.has(requestError.status)
      ) {
        setStudentsUnavailable(true);
      } else {
        setStudentsError(
          requestError instanceof Error
            ? requestError.message
            : "Не удалось загрузить список учеников"
        );
      }
    } finally {
      setStudentsLoading(false);
    }
  }, []);

  const loadTeachersLookup = useCallback(async () => {
    setTeachersLoading(true);
    setTeachersError(null);
    setTeachersUnavailable(false);

    try {
      const items: TeacherListItem[] = [];
      let offset = 0;
      const limit = 200;

      while (true) {
        const page = await listTeachers({ limit, offset });
        items.push(...page.items);
        offset += page.items.length;

        if (page.items.length < limit || items.length >= page.total) {
          break;
        }
      }

      setTeachers(items);
    } catch (requestError) {
      if (
        requestError instanceof ApiClientError &&
        UNAVAILABLE_STATUSES.has(requestError.status)
      ) {
        setTeachersUnavailable(true);
        setTeachers([]);
      } else {
        setTeachersError(
          requestError instanceof Error
            ? requestError.message
            : "Не удалось загрузить список преподавателей"
        );
      }
    } finally {
      setTeachersLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedStudentId) {
      localStorage.removeItem(ADMIN_STUDENT_FILTER_STORAGE_KEY);
      persistSelectedStudent(null);
      return;
    }
    localStorage.setItem(ADMIN_STUDENT_FILTER_STORAGE_KEY, selectedStudentId);
  }, [selectedStudentId]);

  useEffect(() => {
    if (!selectedStudentId || !selectedStudentProfile || selectedStudentProfile.user_id !== selectedStudentId) {
      persistSelectedStudent(null);
      return;
    }
    persistSelectedStudent(selectedStudentProfile);
  }, [selectedStudentId, selectedStudentProfile]);

  useEffect(() => {
    if (!isPickerOpen) {
      return;
    }
    void loadStudentsForPicker();
  }, [isPickerOpen, loadStudentsForPicker]);

  useEffect(() => {
    if (!selectedStudentId) {
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
  }, [selectedStudentId]);

  useEffect(() => {
    if (!selectedStudentId || students.length === 0) {
      return;
    }
    const found = students.find((item) => item.user_id === selectedStudentId);
    if (found) {
      setSelectedStudentProfile(found);
    }
  }, [selectedStudentId, students]);

  useEffect(() => {
    if (bookings.length === 0 || teachers.length > 0 || teachersLoading || teachersUnavailable) {
      return;
    }
    void loadTeachersLookup();
  }, [bookings.length, loadTeachersLookup, teachers.length, teachersLoading, teachersUnavailable]);

  const selectedStudent = useMemo(() => {
    const fromList = students.find((item) => item.user_id === selectedStudentId) ?? null;
    if (fromList) {
      return fromList;
    }
    if (selectedStudentProfile && selectedStudentProfile.user_id === selectedStudentId) {
      return selectedStudentProfile;
    }
    return null;
  }, [selectedStudentId, selectedStudentProfile, students]);

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

  return (
    <section className="teachers-grid students-grid">
      <article className="card students-card students-picker-card">
        <p className="eyebrow">Студенты</p>
        <h1>Выбор ученика</h1>

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

        <div className="quick-filter-group" role="group" aria-label="Выбор ученика из списка">
          <button
            type="button"
            className="quick-filter active"
            onClick={() => setIsPickerOpen(true)}
          >
            Открыть список
          </button>
          <button
            type="button"
            className="quick-filter"
            onClick={() => {
              setSelectedStudentId(null);
              setSelectedStudentProfile(null);
            }}
            disabled={!selectedStudentId}
          >
            Сбросить выбор
          </button>
        </div>

        <p className="summary">
          Выбран: <strong>{selectedStudent?.full_name ?? selectedStudentId ?? "не выбран"}</strong>
        </p>

        {studentsUnavailable ? (
          <p className="summary">`GET /admin/users?role=student` недоступен в текущем backend-контракте.</p>
        ) : null}
        {studentsError ? <p className="error-text">{studentsError}</p> : null}
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
          <p className="summary">Выберите ученика через кнопку "Открыть список".</p>
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
                        {pkg.price_amount ? `${pkg.price_amount} ${pkg.price_currency ?? ""}` : "-"}
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
                      <td>{item.nextAtUtc ? formatDateTime(item.nextAtUtc, selectedStudent?.timezone) : "-"}</td>
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
                          {formatWeekday(booking.slot_start_at_utc, selectedStudent?.timezone ?? "UTC")}{" "}
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

      {isPickerOpen ? (
        <div className="modal-backdrop">
          <div className="modal-card students-picker-modal">
            <h2>Список учеников</h2>

            <label>
              <span>Поиск (ФИО / почта / ID)</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="например, student@... или Иванов"
              />
            </label>

            {studentsLoading ? <p className="summary">Загрузка списка...</p> : null}
            {studentsError ? <p className="error-text">{studentsError}</p> : null}
            {studentsUnavailable ? (
              <p className="summary">`GET /admin/users?role=student` недоступен в текущем backend-контракте.</p>
            ) : null}

            {!studentsLoading && !studentsUnavailable ? (
              filteredStudents.length ? (
                <div className="teacher-list students-list students-picker-list">
                  {filteredStudents.map((student) => (
                    <button
                      key={student.user_id}
                      type="button"
                      className={
                        student.user_id === selectedStudentId ? "teacher-item active" : "teacher-item"
                      }
                      onClick={() => {
                        setSelectedStudentId(student.user_id);
                        setSelectedStudentProfile(student);
                        setIsPickerOpen(false);
                      }}
                    >
                      <strong>{student.full_name}</strong>
                      <span>{student.email}</span>
                      <span>{student.timezone}</span>
                      <span>{student.is_active ? "активен" : "отключён"}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="summary">По выбранным фильтрам ученики не найдены.</p>
              )
            ) : null}

            <div className="modal-actions">
              <button type="button" onClick={() => setIsPickerOpen(false)}>
                Закрыть
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
