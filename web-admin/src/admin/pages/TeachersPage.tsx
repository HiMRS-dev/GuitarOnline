import { useCallback, useEffect, useMemo, useState } from "react";

import {
  activateTeacher,
  disableTeacher,
  getTeacherDetail,
  getTeacherSchedule,
  invalidateTeachersCache,
  listTeachers,
  updateTeacherSchedule
} from "../../features/teachers/api";
import type {
  TeacherDetail,
  TeacherListItem,
  TeacherSchedule,
  TeacherScheduleWindowWrite
} from "../../features/teachers/types";
import { ApiClientError } from "../../shared/api/client";
import {
  ADMIN_TEACHERS_STATUS_STORAGE_KEY,
  ADMIN_TEACHER_FILTER_STORAGE_KEY
} from "../../shared/storage/adminFilters";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);
type TeacherStatusFilter = "all" | "active" | "disabled";

const STATUS_FILTER_OPTIONS: Array<{ value: TeacherStatusFilter; label: string }> = [
  { value: "all", label: "Все" },
  { value: "active", label: "Активные" },
  { value: "disabled", label: "Отключённые" }
];

const TEACHER_STATUS_LABELS: Record<string, string> = {
  active: "активен",
  disabled: "отключён"
};

const WEEKDAY_OPTIONS: Array<{ value: number; label: string }> = [
  { value: 0, label: "Понедельник" },
  { value: 1, label: "Вторник" },
  { value: 2, label: "Среда" },
  { value: 3, label: "Четверг" },
  { value: 4, label: "Пятница" },
  { value: 5, label: "Суббота" },
  { value: 6, label: "Воскресенье" }
];

function normalizeStatusFilter(value: string | null): TeacherStatusFilter {
  if (value === "active" || value === "disabled") {
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

function formatWeekday(weekday: number): string {
  return WEEKDAY_OPTIONS.find((item) => item.value === weekday)?.label ?? `День ${weekday}`;
}

function toInputTime(value: string): string {
  const [hours = "00", minutes = "00"] = value.split(":");
  return `${hours.padStart(2, "0")}:${minutes.padStart(2, "0")}`;
}

function toApiTime(value: string): string {
  return value.length === 5 ? `${value}:00` : value;
}

function toMinutes(value: string): number {
  const [hours, minutes] = value.split(":").map((item) => Number(item));
  return hours * 60 + minutes;
}

function sortScheduleDraft(items: TeacherScheduleWindowWrite[]): TeacherScheduleWindowWrite[] {
  return [...items].sort((left, right) => {
    if (left.weekday !== right.weekday) {
      return left.weekday - right.weekday;
    }
    return (
      toMinutes(toInputTime(left.start_local_time)) - toMinutes(toInputTime(right.start_local_time))
    );
  });
}

export function TeachersPage() {
  const [selectedTeacherId, setSelectedTeacherId] = useState<string | null>(
    () => localStorage.getItem(ADMIN_TEACHER_FILTER_STORAGE_KEY) || null
  );
  const [statusFilter, setStatusFilter] = useState<TeacherStatusFilter>(() =>
    normalizeStatusFilter(localStorage.getItem(ADMIN_TEACHERS_STATUS_STORAGE_KEY))
  );
  const [teacherSearch, setTeacherSearch] = useState("");
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const [pickerTeachers, setPickerTeachers] = useState<TeacherListItem[]>([]);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerError, setPickerError] = useState<string | null>(null);
  const [pickerUnavailable, setPickerUnavailable] = useState(false);

  const [teacherDetail, setTeacherDetail] = useState<TeacherDetail | null>(null);
  const [teacherSchedule, setTeacherSchedule] = useState<TeacherSchedule | null>(null);
  const [scheduleDraft, setScheduleDraft] = useState<TeacherScheduleWindowWrite[]>([]);
  const [newWindowWeekday, setNewWindowWeekday] = useState<number>(1);
  const [newWindowStart, setNewWindowStart] = useState("10:00");
  const [newWindowEnd, setNewWindowEnd] = useState("16:00");

  const [detailLoading, setDetailLoading] = useState(false);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [scheduleSaving, setScheduleSaving] = useState(false);

  const [detailError, setDetailError] = useState<string | null>(null);
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [scheduleSaveSuccess, setScheduleSaveSuccess] = useState<string | null>(null);

  const [actionPending, setActionPending] = useState<"disable" | "activate" | null>(null);

  const loadTeachersForPicker = useCallback(async () => {
    setPickerLoading(true);
    setPickerError(null);
    setPickerUnavailable(false);

    try {
      const items: TeacherListItem[] = [];
      let offset = 0;
      const limit = 100;
      while (true) {
        const page = await listTeachers(
          statusFilter === "all"
            ? { limit, offset }
            : { status: statusFilter, limit, offset }
        );
        items.push(...page.items);
        offset += page.items.length;

        if (page.items.length < limit || items.length >= page.total) {
          break;
        }
      }
      setPickerTeachers(items);
    } catch (requestError) {
      if (
        requestError instanceof ApiClientError &&
        UNAVAILABLE_STATUSES.has(requestError.status)
      ) {
        setPickerUnavailable(true);
      } else {
        setPickerError(
          requestError instanceof Error
            ? requestError.message
            : "Не удалось загрузить список преподавателей"
        );
      }
    } finally {
      setPickerLoading(false);
    }
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
    setPickerTeachers([]);
  }, [statusFilter]);

  useEffect(() => {
    if (!isPickerOpen) {
      return;
    }
    void loadTeachersForPicker();
  }, [isPickerOpen, loadTeachersForPicker]);

  useEffect(() => {
    if (isPickerOpen || !teacherSearch.trim()) {
      return;
    }
    if (pickerTeachers.length > 0 || pickerLoading || pickerUnavailable) {
      return;
    }
    void loadTeachersForPicker();
  }, [
    isPickerOpen,
    loadTeachersForPicker,
    pickerLoading,
    pickerTeachers.length,
    pickerUnavailable,
    teacherSearch
  ]);

  useEffect(() => {
    if (!selectedTeacherId) {
      setTeacherDetail(null);
      setTeacherSchedule(null);
      setScheduleDraft([]);
      setDetailError(null);
      setScheduleError(null);
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
          setTeacherDetail(null);
          setDetailError(
            requestError instanceof Error ? requestError.message : "Не удалось загрузить данные"
          );
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
  }, [selectedTeacherId]);

  useEffect(() => {
    if (!selectedTeacherId) {
      setTeacherSchedule(null);
      setScheduleDraft([]);
      setScheduleError(null);
      setScheduleSaveSuccess(null);
      return;
    }

    let active = true;
    setScheduleLoading(true);
    setScheduleError(null);
    setScheduleSaveSuccess(null);

    getTeacherSchedule(selectedTeacherId)
      .then((schedule) => {
        if (!active) {
          return;
        }
        setTeacherSchedule(schedule);
        setScheduleDraft(
          schedule.windows.map((item) => ({
            weekday: item.weekday,
            start_local_time: toInputTime(item.start_local_time),
            end_local_time: toInputTime(item.end_local_time)
          }))
        );
      })
      .catch((requestError) => {
        if (!active) {
          return;
        }
        setTeacherSchedule(null);
        setScheduleDraft([]);
        setScheduleError(
          requestError instanceof Error
            ? requestError.message
            : "Не удалось загрузить график преподавателя"
        );
      })
      .finally(() => {
        if (active) {
          setScheduleLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [selectedTeacherId]);

  const filteredPickerTeachers = useMemo(() => {
    const normalizedQuery = teacherSearch.trim().toLowerCase();
    if (!normalizedQuery) {
      return pickerTeachers;
    }
    return pickerTeachers.filter((teacher) => {
      return (
        teacher.display_name.toLowerCase().includes(normalizedQuery) ||
        teacher.full_name.toLowerCase().includes(normalizedQuery) ||
        teacher.email.toLowerCase().includes(normalizedQuery)
      );
    });
  }, [pickerTeachers, teacherSearch]);

  const teacherSuggestions = useMemo(() => {
    if (isPickerOpen || !teacherSearch.trim()) {
      return [];
    }
    return filteredPickerTeachers.slice(0, 6);
  }, [filteredPickerTeachers, isPickerOpen, teacherSearch]);

  const selectedTeacherFromPicker = useMemo(
    () => pickerTeachers.find((item) => item.teacher_id === selectedTeacherId) ?? null,
    [pickerTeachers, selectedTeacherId]
  );

  async function handleDisableAction() {
    if (!selectedTeacherId) {
      return;
    }

    setActionPending("disable");
    setActionError(null);
    setActionSuccess(null);

    try {
      invalidateTeachersCache();
      const updatedDetail = await disableTeacher(selectedTeacherId);
      setTeacherDetail(updatedDetail);

      if (isPickerOpen) {
        await loadTeachersForPicker();
      }

      if (!isValidTeacherStatusFilter(updatedDetail.status, statusFilter)) {
        setActionSuccess("Статус обновлён. Преподаватель скрыт текущим фильтром.");
      } else {
        setActionSuccess("Преподаватель отключён, вход заблокирован.");
      }
    } catch (requestError) {
      setActionError(
        requestError instanceof Error
          ? requestError.message
          : "Не удалось отключить преподавателя"
      );
    } finally {
      setActionPending(null);
    }
  }

  async function handleActivateAction() {
    if (!selectedTeacherId) {
      return;
    }

    setActionPending("activate");
    setActionError(null);
    setActionSuccess(null);

    try {
      invalidateTeachersCache();
      await activateTeacher(selectedTeacherId);
      const updatedDetail = await getTeacherDetail(selectedTeacherId);
      setTeacherDetail(updatedDetail);

      if (isPickerOpen) {
        await loadTeachersForPicker();
      }

      if (!isValidTeacherStatusFilter(updatedDetail.status, statusFilter)) {
        setActionSuccess("Статус обновлён. Преподаватель скрыт текущим фильтром.");
      } else {
        setActionSuccess("Преподаватель снова активен, вход разблокирован.");
      }
    } catch (requestError) {
      setActionError(
        requestError instanceof Error
          ? requestError.message
          : "Не удалось снова активировать преподавателя"
      );
    } finally {
      setActionPending(null);
    }
  }

  function handleAddScheduleWindow() {
    const normalizedStart = toInputTime(newWindowStart);
    const normalizedEnd = toInputTime(newWindowEnd);
    if (toMinutes(normalizedEnd) <= toMinutes(normalizedStart)) {
      setScheduleError("Время окончания должно быть позже времени начала");
      return;
    }

    const hasOverlap = scheduleDraft.some((item) => {
      if (item.weekday !== newWindowWeekday) {
        return false;
      }
      const existingStart = toMinutes(toInputTime(item.start_local_time));
      const existingEnd = toMinutes(toInputTime(item.end_local_time));
      const nextStart = toMinutes(normalizedStart);
      const nextEnd = toMinutes(normalizedEnd);
      return nextStart < existingEnd && nextEnd > existingStart;
    });
    if (hasOverlap) {
      setScheduleError("Для выбранного дня есть пересекающийся интервал");
      return;
    }

    setScheduleError(null);
    setScheduleSaveSuccess(null);
    setScheduleDraft((current) =>
      sortScheduleDraft(
        current.concat({
          weekday: newWindowWeekday,
          start_local_time: normalizedStart,
          end_local_time: normalizedEnd
        })
      )
    );
  }

  function handleRemoveScheduleWindow(index: number) {
    setScheduleError(null);
    setScheduleSaveSuccess(null);
    setScheduleDraft((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  function resetScheduleDraft() {
    setScheduleError(null);
    setScheduleSaveSuccess(null);
    setScheduleDraft(
      (teacherSchedule?.windows ?? []).map((item) => ({
        weekday: item.weekday,
        start_local_time: toInputTime(item.start_local_time),
        end_local_time: toInputTime(item.end_local_time)
      }))
    );
  }

  async function handleSaveSchedule() {
    if (!selectedTeacherId) {
      return;
    }
    setScheduleSaving(true);
    setScheduleError(null);
    setScheduleSaveSuccess(null);
    try {
      const payload: TeacherScheduleWindowWrite[] = sortScheduleDraft(scheduleDraft).map((item) => ({
        weekday: item.weekday,
        start_local_time: toApiTime(toInputTime(item.start_local_time)),
        end_local_time: toApiTime(toInputTime(item.end_local_time))
      }));
      const updated = await updateTeacherSchedule(selectedTeacherId, { windows: payload });
      setTeacherSchedule(updated);
      setScheduleDraft(
        updated.windows.map((item) => ({
          weekday: item.weekday,
          start_local_time: toInputTime(item.start_local_time),
          end_local_time: toInputTime(item.end_local_time)
        }))
      );
      setScheduleSaveSuccess("Постоянный график сохранён");
    } catch (requestError) {
      setScheduleError(
        requestError instanceof Error
          ? requestError.message
          : "Не удалось сохранить график преподавателя"
      );
    } finally {
      setScheduleSaving(false);
    }
  }

  return (
    <section className="teachers-grid">
      <article className="card teachers-picker-card">
        <p className="eyebrow">Преподаватели</p>
        <h1>Выбор преподавателя</h1>

        <label className="teachers-picker-search">
          <span>Поиск преподавателя</span>
          <input
            type="search"
            value={teacherSearch}
            onChange={(event) => setTeacherSearch(event.target.value)}
            placeholder="например, jazz или teacher@..."
          />
        </label>
        {teacherSearch.trim() ? (
          <div className="picker-search-suggestions">
            {pickerLoading ? <p className="summary">Загружаем подсказки...</p> : null}
            {!pickerLoading && !pickerUnavailable && teacherSuggestions.length ? (
              <div className="picker-suggestion-list">
                {teacherSuggestions.map((teacher) => (
                  <div key={teacher.teacher_id} className="picker-suggestion-item">
                    <div className="picker-suggestion-meta">
                      <strong>{teacher.full_name}</strong>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedTeacherId(teacher.teacher_id);
                        setTeacherSearch("");
                      }}
                    >
                      Выбрать
                    </button>
                  </div>
                ))}
              </div>
            ) : null}
            {!pickerLoading &&
            !pickerUnavailable &&
            !pickerError &&
            teacherSuggestions.length === 0 ? (
              <p className="summary">Совпадений не найдено.</p>
            ) : null}
          </div>
        ) : null}

        <div
          className="quick-filter-group"
          role="group"
          aria-label="Фильтры статуса преподавателей"
        >
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

        <div className="quick-filter-group" role="group" aria-label="Выбор преподавателя из списка">
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
            onClick={() => setSelectedTeacherId(null)}
            disabled={!selectedTeacherId}
          >
            Сбросить выбор
          </button>
        </div>

        <p className="summary">
          Выбран: <strong>{teacherDetail?.display_name ?? selectedTeacherFromPicker?.display_name ?? "не выбран"}</strong>
        </p>

        {pickerUnavailable ? (
          <p className="summary">`GET /admin/teachers` недоступен в текущем backend-контракте.</p>
        ) : null}
        {pickerError ? <p className="error-text">{pickerError}</p> : null}
      </article>

      <article className="card teachers-card-detail">
        <p className="eyebrow">Карточка преподавателя</p>
        {teacherDetail ? <h1>{teacherDetail.display_name}</h1> : <h1>Не выбрано</h1>}

        <div className="quick-filter-group" role="group" aria-label="Действия по аккаунту преподавателя">
          {statusFilter !== "disabled" ? (
            <button
              type="button"
              className="quick-filter"
              disabled={!teacherDetail || actionPending !== null || teacherDetail.status === "disabled"}
              onClick={() => void handleDisableAction()}
            >
              {actionPending === "disable" ? "Отключение..." : "Отключить"}
            </button>
          ) : null}
          {statusFilter !== "active" ? (
            <button
              type="button"
              className="quick-filter"
              disabled={!teacherDetail || actionPending !== null || teacherDetail.status === "active"}
              onClick={() => void handleActivateAction()}
            >
              {actionPending === "activate" ? "Активируем..." : "Активировать"}
            </button>
          ) : null}
        </div>

        {detailLoading ? <p className="summary">Загрузка данных преподавателя...</p> : null}
        {detailError ? <p className="error-text">{detailError}</p> : null}
        {actionError ? <p className="error-text">{actionError}</p> : null}
        {actionSuccess ? <p className="success-text">{actionSuccess}</p> : null}

        {teacherDetail ? (
          <div className="teacher-detail">
            <p>
              <strong>ФИО:</strong> {teacherDetail.full_name}
            </p>
            <p>
              <strong>Статус:</strong> {formatTeacherStatus(teacherDetail.status)}
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
              <strong>Таймзона:</strong> {teacherDetail.timezone}
            </p>
            <p>
              <strong>Теги:</strong> {teacherDetail.tags.length ? teacherDetail.tags.join(", ") : "нет"}
            </p>
            <p>
              <strong>О себе:</strong> {teacherDetail.bio}
            </p>
          </div>
        ) : (
          <p className="summary">Выберите преподавателя через кнопку "Открыть список".</p>
        )}

        <section className="teacher-schedule-block">
          <h2>Постоянный график преподавателя</h2>
          {teacherSchedule ? (
            <p className="summary">
              Локальная зона: <code>{teacherSchedule.timezone}</code>, вторая зона: <code>Europe/Moscow</code>.
            </p>
          ) : null}
          {scheduleLoading ? <p className="summary">Загрузка графика...</p> : null}
          {scheduleError ? <p className="error-text">{scheduleError}</p> : null}
          {scheduleSaveSuccess ? <p className="success-text">{scheduleSaveSuccess}</p> : null}

          {!scheduleLoading && selectedTeacherId ? (
            <div className="teacher-schedule-editor">
              <div className="teacher-schedule-row">
                <label>
                  <span>День недели</span>
                  <select
                    value={newWindowWeekday}
                    onChange={(event) => setNewWindowWeekday(Number(event.target.value))}
                    disabled={scheduleSaving}
                  >
                    {WEEKDAY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Начало (локальное)</span>
                  <input
                    type="time"
                    value={newWindowStart}
                    onChange={(event) => setNewWindowStart(event.target.value)}
                    disabled={scheduleSaving}
                  />
                </label>
                <label>
                  <span>Конец (локальное)</span>
                  <input
                    type="time"
                    value={newWindowEnd}
                    onChange={(event) => setNewWindowEnd(event.target.value)}
                    disabled={scheduleSaving}
                  />
                </label>
                <button
                  type="button"
                  className="quick-filter"
                  onClick={handleAddScheduleWindow}
                  disabled={scheduleSaving}
                >
                  Добавить интервал
                </button>
              </div>

              {scheduleDraft.length ? (
                <div className="bookings-table-wrap">
                  <table className="bookings-table teacher-schedule-table">
                    <thead>
                      <tr>
                        <th>День</th>
                        <th>Локальное время</th>
                        <th>Действие</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortScheduleDraft(scheduleDraft).map((item, index) => (
                        <tr key={`${item.weekday}-${item.start_local_time}-${item.end_local_time}-${index}`}>
                          <td>{formatWeekday(item.weekday)}</td>
                          <td>
                            {toInputTime(item.start_local_time)} - {toInputTime(item.end_local_time)}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="quick-filter"
                              onClick={() => handleRemoveScheduleWindow(index)}
                              disabled={scheduleSaving}
                            >
                              Удалить
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="summary">В черновике графика пока нет интервалов.</p>
              )}

              <div className="quick-filter-group" role="group" aria-label="Действия графика преподавателя">
                <button
                  type="button"
                  className="quick-filter"
                  onClick={resetScheduleDraft}
                  disabled={scheduleSaving}
                >
                  Сбросить черновик
                </button>
                <button
                  type="button"
                  className="quick-filter active"
                  onClick={() => void handleSaveSchedule()}
                  disabled={scheduleSaving}
                >
                  {scheduleSaving ? "Сохраняем..." : "Сохранить постоянный график"}
                </button>
              </div>
            </div>
          ) : null}

          {!scheduleLoading && teacherSchedule ? (
            teacherSchedule.windows.length ? (
              <div className="bookings-table-wrap">
                <table className="bookings-table teacher-schedule-table">
                  <thead>
                    <tr>
                      <th>Локальное ({teacherSchedule.timezone})</th>
                      <th>Московское (Europe/Moscow)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {teacherSchedule.windows.map((item) => (
                      <tr key={item.schedule_window_id}>
                        <td>
                          {formatWeekday(item.weekday)} {toInputTime(item.start_local_time)} -{" "}
                          {toInputTime(item.end_local_time)}
                        </td>
                        <td>
                          {formatWeekday(item.moscow_start_weekday)} {toInputTime(item.moscow_start_time)} -{" "}
                          {formatWeekday(item.moscow_end_weekday)} {toInputTime(item.moscow_end_time)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="summary">Сохранённый график пока пуст.</p>
            )
          ) : null}
        </section>
      </article>

      {isPickerOpen ? (
        <div className="modal-backdrop">
          <div className="modal-card teachers-picker-modal">
            <h2>Список преподавателей</h2>

            <label>
              <span>Поиск преподавателя</span>
              <input
                type="search"
                value={teacherSearch}
                onChange={(event) => setTeacherSearch(event.target.value)}
                placeholder="например, jazz или teacher@..."
              />
            </label>

            {pickerLoading ? <p className="summary">Загрузка списка...</p> : null}
            {pickerError ? <p className="error-text">{pickerError}</p> : null}
            {pickerUnavailable ? (
              <p className="summary">`GET /admin/teachers` недоступен в текущем backend-контракте.</p>
            ) : null}

            {!pickerLoading && !pickerUnavailable ? (
              filteredPickerTeachers.length ? (
                <div className="teacher-list teacher-picker-list">
                  {filteredPickerTeachers.map((teacher) => (
                    <button
                      key={teacher.teacher_id}
                      type="button"
                      className={
                        teacher.teacher_id === selectedTeacherId ? "teacher-item active" : "teacher-item"
                      }
                      onClick={() => {
                        setSelectedTeacherId(teacher.teacher_id);
                        setIsPickerOpen(false);
                      }}
                    >
                      <strong>{teacher.full_name}</strong>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="summary">По выбранным фильтрам преподаватели не найдены.</p>
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
