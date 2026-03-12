import interactionPlugin from "@fullcalendar/interaction";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import ruLocale from "@fullcalendar/core/locales/ru";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiClientError } from "../../shared/api/client";
import { ADMIN_TEACHER_FILTER_STORAGE_KEY } from "../../shared/storage/adminFilters";
import {
  cancelAdminBooking,
  listAdminBookings,
  rescheduleAdminBooking
} from "../../features/bookings/api";
import type { AdminBooking } from "../../features/bookings/types";
import { listTeachers } from "../../features/teachers/api";
import type { TeacherListItem } from "../../features/teachers/types";
import {
  blockAdminSlot,
  bulkCreateAdminSlots,
  createAdminSlot,
  listAdminSlots
} from "../../features/slots/api";
import type { AdminSlot } from "../../features/slots/types";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);

const SLOT_STATUS_META: Record<AdminSlot["slot_status"], { label: string; color: string }> = {
  open: { label: "Открыт", color: "#17a34a" },
  hold: { label: "На удержании", color: "#d5921d" },
  booked: { label: "Подтвержден", color: "#205ea2" },
  blocked: { label: "Заблокирован", color: "#a13232" },
  canceled: { label: "Отменен", color: "#7a8795" }
};

const BOOKING_STATUS_LABELS: Record<string, string> = {
  hold: "на удержании",
  booked: "подтверждено",
  confirmed: "подтверждено",
  canceled: "отменено",
  completed: "завершено",
  no_show: "неявка"
};

function formatBookingStatus(status: string): string {
  return BOOKING_STATUS_LABELS[status] ?? status;
}

type UtcRange = {
  fromUtc: string;
  toUtc: string;
};

function buildInitialRange(): UtcRange {
  const start = new Date();
  const end = new Date(start);
  end.setDate(end.getDate() + 7);
  return {
    fromUtc: start.toISOString(),
    toUtc: end.toISOString()
  };
}

function toIso(value: string): string {
  return new Date(value).toISOString();
}

function toApiTime(value: string): string {
  return value.length === 5 ? `${value}:00` : value;
}

export function CalendarPage() {
  const [teachers, setTeachers] = useState<TeacherListItem[]>([]);
  const [teacherId, setTeacherId] = useState(
    () => localStorage.getItem(ADMIN_TEACHER_FILTER_STORAGE_KEY) || ""
  );
  const [range, setRange] = useState<UtcRange>(() => buildInitialRange());
  const [slots, setSlots] = useState<AdminSlot[]>([]);
  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null);
  const [bookings, setBookings] = useState<AdminBooking[]>([]);
  const [bookingsLoading, setBookingsLoading] = useState(false);

  const [teachersUnavailable, setTeachersUnavailable] = useState(false);
  const [slotsUnavailable, setSlotsUnavailable] = useState(false);
  const [bookingsUnavailable, setBookingsUnavailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [showBlock, setShowBlock] = useState(false);
  const [showBulk, setShowBulk] = useState(false);
  const [showCancel, setShowCancel] = useState(false);
  const [showReschedule, setShowReschedule] = useState(false);

  const [createStart, setCreateStart] = useState("");
  const [createEnd, setCreateEnd] = useState("");
  const [blockReason, setBlockReason] = useState("");
  const [cancelBookingId, setCancelBookingId] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [rescheduleBookingId, setRescheduleBookingId] = useState("");
  const [rescheduleSlotId, setRescheduleSlotId] = useState("");
  const [rescheduleReason, setRescheduleReason] = useState("");

  const [bulkDateFrom, setBulkDateFrom] = useState("");
  const [bulkDateTo, setBulkDateTo] = useState("");
  const [bulkStartTime, setBulkStartTime] = useState("10:00");
  const [bulkEndTime, setBulkEndTime] = useState("16:00");
  const [bulkDuration, setBulkDuration] = useState(60);
  const [bulkWeekdays, setBulkWeekdays] = useState<number[]>([1, 2, 3, 4, 5]);

  useEffect(() => {
    let active = true;
    listTeachers()
      .then((page) => {
        if (!active) {
          return;
        }
        setTeachers(page.items);
        if (!teacherId && page.items[0]) {
          setTeacherId(page.items[0].teacher_id);
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
          return;
        }
        setError(
          requestError instanceof Error ? requestError.message : "Не удалось загрузить преподавателей"
        );
      });
    return () => {
      active = false;
    };
  }, [teacherId]);

  useEffect(() => {
    if (!teacherId) {
      return;
    }
    localStorage.setItem(ADMIN_TEACHER_FILTER_STORAGE_KEY, teacherId);
  }, [teacherId]);

  const loadSlots = useCallback(() => {
    if (!teacherId) {
      setSlots([]);
      setLoading(false);
      return Promise.resolve();
    }

    setLoading(true);
    setError(null);
    return listAdminSlots({
      teacherId,
      fromUtc: range.fromUtc,
      toUtc: range.toUtc
    })
      .then((page) => {
        setSlots(page.items);
      })
      .catch((requestError) => {
        if (
          requestError instanceof ApiClientError &&
          UNAVAILABLE_STATUSES.has(requestError.status)
        ) {
          setSlotsUnavailable(true);
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "Не удалось загрузить слоты");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [range.fromUtc, range.toUtc, teacherId]);

  const loadBookings = useCallback(() => {
    if (!teacherId) {
      setBookings([]);
      setBookingsLoading(false);
      return Promise.resolve();
    }

    setBookingsLoading(true);
    return listAdminBookings({
      teacherId,
      fromUtc: range.fromUtc,
      toUtc: range.toUtc
    })
      .then((page) => {
        setBookings(page.items);
      })
      .catch((requestError) => {
        if (
          requestError instanceof ApiClientError &&
          UNAVAILABLE_STATUSES.has(requestError.status)
        ) {
          setBookingsUnavailable(true);
          return;
        }
        setError(
          requestError instanceof Error ? requestError.message : "Не удалось загрузить бронирования"
        );
      })
      .finally(() => {
        setBookingsLoading(false);
      });
  }, [range.fromUtc, range.toUtc, teacherId]);

  useEffect(() => {
    if (teachersUnavailable || slotsUnavailable || bookingsUnavailable) {
      return;
    }
    void loadSlots();
    void loadBookings();
  }, [bookingsUnavailable, loadBookings, loadSlots, slotsUnavailable, teachersUnavailable]);

  const events = useMemo(
    () =>
      slots.map((slot) => ({
        id: slot.slot_id,
        title: SLOT_STATUS_META[slot.slot_status].label,
        start: slot.start_at_utc,
        end: slot.end_at_utc,
        backgroundColor: SLOT_STATUS_META[slot.slot_status].color,
        borderColor: SLOT_STATUS_META[slot.slot_status].color
      })),
    [slots]
  );

  async function handleCreateSlot() {
    if (!teacherId || !createStart || !createEnd) {
      return;
    }
    setActionError(null);
    try {
      await createAdminSlot({
        teacher_id: teacherId,
        start_at_utc: toIso(createStart),
        end_at_utc: toIso(createEnd)
      });
      setShowCreate(false);
      setCreateStart("");
      setCreateEnd("");
      await loadSlots();
    } catch (requestError) {
      setActionError(
        requestError instanceof Error ? requestError.message : "Не удалось создать слот"
      );
    }
  }

  async function handleBlockSlot() {
    if (!selectedSlotId || !blockReason.trim()) {
      return;
    }
    setActionError(null);
    try {
      await blockAdminSlot(selectedSlotId, { reason: blockReason.trim() });
      setShowBlock(false);
      setBlockReason("");
      await loadSlots();
    } catch (requestError) {
      setActionError(
        requestError instanceof Error ? requestError.message : "Не удалось заблокировать слот"
      );
    }
  }

  async function handleBulkCreate() {
    if (!teacherId || !bulkDateFrom || !bulkDateTo || bulkWeekdays.length === 0) {
      return;
    }
    setActionError(null);
    try {
      await bulkCreateAdminSlots({
        teacher_id: teacherId,
        date_from_utc: bulkDateFrom,
        date_to_utc: bulkDateTo,
        weekdays: bulkWeekdays,
        start_time_utc: toApiTime(bulkStartTime),
        end_time_utc: toApiTime(bulkEndTime),
        slot_duration_minutes: bulkDuration,
        exclude_dates: [],
        exclude_time_ranges: []
      });
      setShowBulk(false);
      await loadSlots();
    } catch (requestError) {
      setActionError(
        requestError instanceof Error ? requestError.message : "Не удалось создать слоты массово"
      );
    }
  }

  async function handleRescheduleBooking() {
    if (!rescheduleBookingId || !rescheduleSlotId || !rescheduleReason.trim()) {
      return;
    }
    setActionError(null);
    try {
      await rescheduleAdminBooking(rescheduleBookingId, {
        new_slot_id: rescheduleSlotId,
        reason: rescheduleReason.trim()
      });
      setShowReschedule(false);
      setRescheduleBookingId("");
      setRescheduleSlotId("");
      setRescheduleReason("");
      await Promise.all([loadSlots(), loadBookings()]);
    } catch (requestError) {
      setActionError(
        requestError instanceof Error ? requestError.message : "Не удалось перенести бронирование"
      );
    }
  }

  async function handleCancelBooking() {
    if (!cancelBookingId || !cancelReason.trim()) {
      return;
    }
    setActionError(null);
    try {
      await cancelAdminBooking(cancelBookingId, {
        reason: cancelReason.trim()
      });
      setShowCancel(false);
      setCancelBookingId("");
      setCancelReason("");
      await Promise.all([loadSlots(), loadBookings()]);
    } catch (requestError) {
      setActionError(
        requestError instanceof Error ? requestError.message : "Не удалось отменить бронирование"
      );
    }
  }

  const availableSlots = useMemo(
    () => slots.filter((slot) => slot.slot_status === "open"),
    [slots]
  );

  if (teachersUnavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Календарь</p>
        <h1>Эндпоинт недоступен</h1>
        <p className="summary">
          Для календаря требуется <code>GET /admin/teachers</code>, но эндпоинт недоступен.
        </p>
      </article>
    );
  }

  if (slotsUnavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Календарь</p>
        <h1>Эндпоинт недоступен</h1>
        <p className="summary">
          Для работы со слотами требуются
          <code>GET /admin/slots</code>,
          <code>POST /admin/slots</code>,
          <code>POST /admin/slots/{`{slot_id}`}/block</code> и
          <code>POST /admin/slots/bulk-create</code>.
        </p>
      </article>
    );
  }

  return (
    <section className="calendar-page">
      <article className="card calendar-toolbar">
        <div className="calendar-toolbar-controls">
          <label>
            <span>Преподаватель</span>
            <select
              value={teacherId}
              onChange={(event) => {
                setTeacherId(event.target.value);
              }}
            >
              <option value="">Выберите преподавателя</option>
              {teachers.map((teacher) => (
                <option key={teacher.teacher_id} value={teacher.teacher_id}>
                  {teacher.display_name}
                </option>
              ))}
            </select>
          </label>

          <div className="calendar-actions">
            <button type="button" onClick={() => setShowCreate(true)} disabled={!teacherId}>
              Создать слот
            </button>
            <button type="button" onClick={() => setShowBlock(true)} disabled={!selectedSlotId}>
              Заблокировать выбранный
            </button>
            <button type="button" onClick={() => setShowBulk(true)} disabled={!teacherId}>
              Массовое создание
            </button>
          </div>
        </div>

        <div className="calendar-legend">
          {Object.entries(SLOT_STATUS_META).map(([status, meta]) => (
            <span key={status} className="legend-item">
              <i style={{ background: meta.color }} />
              {meta.label}
            </span>
          ))}
        </div>

        {actionError ? <p className="error-text">{actionError}</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
      </article>

      <article className="card">
        {loading ? <p className="summary">Загрузка календаря...</p> : null}
        <FullCalendar
          plugins={[timeGridPlugin, interactionPlugin]}
          locales={[ruLocale]}
          locale="ru"
          initialView="timeGridWeek"
          events={events}
          height="auto"
          eventClick={(arg) => setSelectedSlotId(arg.event.id)}
          datesSet={(arg) => {
            setRange({
              fromUtc: arg.start.toISOString(),
              toUtc: arg.end.toISOString()
            });
          }}
          headerToolbar={{
            left: "prev,next today",
            center: "title",
            right: "timeGridWeek,timeGridDay"
          }}
        />
      </article>

      <article className="card bookings-panel">
        <p className="eyebrow">Бронирования</p>
        <h2>Таблица бронирований</h2>
        {bookingsUnavailable ? (
          <p className="summary">
            Эндпоинт недоступен: ожидаются <code>GET /admin/bookings</code> и
            <code>POST /admin/bookings/{`{id}`}/reschedule</code>,
            <code>POST /admin/bookings/{`{id}`}/cancel</code>.
          </p>
        ) : null}
        {bookingsLoading ? <p className="summary">Загрузка бронирований...</p> : null}
        {!bookingsUnavailable && !bookingsLoading ? (
          bookings.length ? (
            <div className="bookings-table-wrap">
              <table className="bookings-table">
                <thead>
                  <tr>
                    <th>Бронирование</th>
                    <th>Статус</th>
                    <th>Начало (UTC)</th>
                    <th>Слот</th>
                    <th>Действие</th>
                  </tr>
                </thead>
                <tbody>
                  {bookings.map((booking) => (
                    <tr key={booking.booking_id}>
                      <td>{booking.booking_id.slice(0, 8)}</td>
                      <td>{formatBookingStatus(booking.status)}</td>
                      <td>{new Date(booking.slot_start_at_utc).toISOString()}</td>
                      <td>{booking.slot_id.slice(0, 8)}</td>
                      <td>
                        <div className="calendar-actions">
                          <button
                            type="button"
                            onClick={() => {
                              setRescheduleBookingId(booking.booking_id);
                              setRescheduleSlotId(availableSlots[0]?.slot_id ?? "");
                              setRescheduleReason("Перенос из календаря");
                              setShowReschedule(true);
                            }}
                            disabled={!availableSlots.length || booking.status === "canceled"}
                          >
                            Перенести
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setCancelBookingId(booking.booking_id);
                              setCancelReason("Отмена из календаря");
                              setShowCancel(true);
                            }}
                            disabled={booking.status === "canceled"}
                          >
                            Отменить
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="summary">В выбранном диапазоне бронирований нет.</p>
          )
        ) : null}
      </article>

      {showCreate ? (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h2>Создать слот</h2>
            <label>
              <span>Начало (UTC)</span>
              <input
                type="datetime-local"
                value={createStart}
                onChange={(event) => setCreateStart(event.target.value)}
              />
            </label>
            <label>
              <span>Конец (UTC)</span>
              <input
                type="datetime-local"
                value={createEnd}
                onChange={(event) => setCreateEnd(event.target.value)}
              />
            </label>
            <div className="modal-actions">
              <button type="button" onClick={handleCreateSlot}>
                Сохранить
              </button>
              <button type="button" onClick={() => setShowCreate(false)}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showBlock ? (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h2>Блокировка слота</h2>
            <label>
              <span>Причина</span>
              <input value={blockReason} onChange={(event) => setBlockReason(event.target.value)} />
            </label>
            <div className="modal-actions">
              <button type="button" onClick={handleBlockSlot}>
                Заблокировать
              </button>
              <button type="button" onClick={() => setShowBlock(false)}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showBulk ? (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h2>Массовое создание слотов</h2>
            <label>
              <span>Дата с</span>
              <input
                type="date"
                value={bulkDateFrom}
                onChange={(event) => setBulkDateFrom(event.target.value)}
              />
            </label>
            <label>
              <span>Дата по</span>
              <input
                type="date"
                value={bulkDateTo}
                onChange={(event) => setBulkDateTo(event.target.value)}
              />
            </label>
            <label>
              <span>Время начала (UTC)</span>
              <input
                type="time"
                value={bulkStartTime}
                onChange={(event) => setBulkStartTime(event.target.value)}
              />
            </label>
            <label>
              <span>Время окончания (UTC)</span>
              <input
                type="time"
                value={bulkEndTime}
                onChange={(event) => setBulkEndTime(event.target.value)}
              />
            </label>
            <label>
              <span>Длительность (минуты)</span>
              <input
                type="number"
                min={1}
                max={720}
                value={bulkDuration}
                onChange={(event) => setBulkDuration(Number(event.target.value))}
              />
            </label>
            <label>
              <span>Дни недели (0=Пн .. 6=Вс)</span>
              <input
                value={bulkWeekdays.join(",")}
                onChange={(event) => {
                  const parsed = event.target.value
                    .split(",")
                    .map((item) => Number(item.trim()))
                    .filter((item) => Number.isInteger(item) && item >= 0 && item <= 6);
                  setBulkWeekdays(Array.from(new Set(parsed)));
                }}
              />
            </label>
            <div className="modal-actions">
              <button type="button" onClick={handleBulkCreate}>
                Запустить
              </button>
              <button type="button" onClick={() => setShowBulk(false)}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showCancel ? (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h2>Отмена бронирования</h2>
            <label>
              <span>Причина</span>
              <input
                value={cancelReason}
                onChange={(event) => setCancelReason(event.target.value)}
              />
            </label>
            <div className="modal-actions">
              <button type="button" onClick={handleCancelBooking}>
                Отменить бронирование
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowCancel(false);
                  setCancelBookingId("");
                  setCancelReason("");
                }}
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showReschedule ? (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h2>Перенос бронирования</h2>
            <label>
              <span>Новый слот</span>
              <select
                value={rescheduleSlotId}
                onChange={(event) => setRescheduleSlotId(event.target.value)}
              >
                <option value="">Выберите слот</option>
                {availableSlots.map((slot) => (
                  <option key={slot.slot_id} value={slot.slot_id}>
                    {new Date(slot.start_at_utc).toISOString()} - {slot.slot_id.slice(0, 8)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Причина</span>
              <input
                value={rescheduleReason}
                onChange={(event) => setRescheduleReason(event.target.value)}
              />
            </label>
            <div className="modal-actions">
              <button type="button" onClick={handleRescheduleBooking}>
                Перенести
              </button>
              <button type="button" onClick={() => setShowReschedule(false)}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
