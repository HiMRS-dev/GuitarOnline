import interactionPlugin from "@fullcalendar/interaction";
import "@fullcalendar/core/index.css";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import "@fullcalendar/timegrid/index.css";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiClientError } from "../../shared/api/client";
import { listTeachers } from "../../features/teachers/api";
import type { TeacherListItem } from "../../features/teachers/types";
import {
  blockAdminSlot,
  bulkCreateAdminSlots,
  createAdminSlot,
  listAdminSlots
} from "../../features/slots/api";
import type { AdminSlot } from "../../features/slots/types";

const TEACHER_FILTER_STORAGE_KEY = "go_admin_calendar_teacher_id";
const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);

const SLOT_STATUS_META: Record<AdminSlot["slot_status"], { label: string; color: string }> = {
  open: { label: "Open", color: "#17a34a" },
  hold: { label: "Held", color: "#d5921d" },
  booked: { label: "Confirmed", color: "#205ea2" },
  blocked: { label: "Blocked", color: "#a13232" },
  canceled: { label: "Canceled", color: "#7a8795" }
};

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
    () => localStorage.getItem(TEACHER_FILTER_STORAGE_KEY) || ""
  );
  const [range, setRange] = useState<UtcRange>(() => buildInitialRange());
  const [slots, setSlots] = useState<AdminSlot[]>([]);
  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null);

  const [teachersUnavailable, setTeachersUnavailable] = useState(false);
  const [slotsUnavailable, setSlotsUnavailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [showBlock, setShowBlock] = useState(false);
  const [showBulk, setShowBulk] = useState(false);

  const [createStart, setCreateStart] = useState("");
  const [createEnd, setCreateEnd] = useState("");
  const [blockReason, setBlockReason] = useState("");

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
        setError(requestError instanceof Error ? requestError.message : "Failed to load teachers");
      });
    return () => {
      active = false;
    };
  }, [teacherId]);

  useEffect(() => {
    if (!teacherId) {
      return;
    }
    localStorage.setItem(TEACHER_FILTER_STORAGE_KEY, teacherId);
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
        setError(requestError instanceof Error ? requestError.message : "Failed to load slots");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [range.fromUtc, range.toUtc, teacherId]);

  useEffect(() => {
    if (teachersUnavailable || slotsUnavailable) {
      return;
    }
    void loadSlots();
  }, [loadSlots, slotsUnavailable, teachersUnavailable]);

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
        requestError instanceof Error ? requestError.message : "Failed to create slot"
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
      setActionError(requestError instanceof Error ? requestError.message : "Failed to block slot");
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
        requestError instanceof Error ? requestError.message : "Failed to bulk create"
      );
    }
  }

  if (teachersUnavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Calendar</p>
        <h1>Endpoint unavailable</h1>
        <p className="summary">
          Calendar requires <code>GET /admin/teachers</code>, but the endpoint is unavailable.
        </p>
      </article>
    );
  }

  if (slotsUnavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Calendar</p>
        <h1>Endpoint unavailable</h1>
        <p className="summary">
          Slot actions require
          <code>GET /admin/slots</code>,
          <code>POST /admin/slots</code>,
          <code>POST /admin/slots/{`{slot_id}`}/block</code> and
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
            <span>Teacher</span>
            <select
              value={teacherId}
              onChange={(event) => {
                setTeacherId(event.target.value);
              }}
            >
              <option value="">Select teacher</option>
              {teachers.map((teacher) => (
                <option key={teacher.teacher_id} value={teacher.teacher_id}>
                  {teacher.display_name}
                </option>
              ))}
            </select>
          </label>

          <div className="calendar-actions">
            <button type="button" onClick={() => setShowCreate(true)} disabled={!teacherId}>
              Create slot
            </button>
            <button type="button" onClick={() => setShowBlock(true)} disabled={!selectedSlotId}>
              Block selected
            </button>
            <button type="button" onClick={() => setShowBulk(true)} disabled={!teacherId}>
              Bulk create
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
        {loading ? <p className="summary">Loading calendar...</p> : null}
        <FullCalendar
          plugins={[timeGridPlugin, interactionPlugin]}
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

      {showCreate ? (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h2>Create Slot</h2>
            <label>
              <span>Start (UTC)</span>
              <input
                type="datetime-local"
                value={createStart}
                onChange={(event) => setCreateStart(event.target.value)}
              />
            </label>
            <label>
              <span>End (UTC)</span>
              <input
                type="datetime-local"
                value={createEnd}
                onChange={(event) => setCreateEnd(event.target.value)}
              />
            </label>
            <div className="modal-actions">
              <button type="button" onClick={handleCreateSlot}>
                Save
              </button>
              <button type="button" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showBlock ? (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h2>Block Slot</h2>
            <label>
              <span>Reason</span>
              <input value={blockReason} onChange={(event) => setBlockReason(event.target.value)} />
            </label>
            <div className="modal-actions">
              <button type="button" onClick={handleBlockSlot}>
                Block
              </button>
              <button type="button" onClick={() => setShowBlock(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showBulk ? (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h2>Bulk Create Slots</h2>
            <label>
              <span>Date from</span>
              <input
                type="date"
                value={bulkDateFrom}
                onChange={(event) => setBulkDateFrom(event.target.value)}
              />
            </label>
            <label>
              <span>Date to</span>
              <input
                type="date"
                value={bulkDateTo}
                onChange={(event) => setBulkDateTo(event.target.value)}
              />
            </label>
            <label>
              <span>Start time (UTC)</span>
              <input
                type="time"
                value={bulkStartTime}
                onChange={(event) => setBulkStartTime(event.target.value)}
              />
            </label>
            <label>
              <span>End time (UTC)</span>
              <input
                type="time"
                value={bulkEndTime}
                onChange={(event) => setBulkEndTime(event.target.value)}
              />
            </label>
            <label>
              <span>Duration (minutes)</span>
              <input
                type="number"
                min={1}
                max={720}
                value={bulkDuration}
                onChange={(event) => setBulkDuration(Number(event.target.value))}
              />
            </label>
            <label>
              <span>Weekdays (0=Mon .. 6=Sun)</span>
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
                Run
              </button>
              <button type="button" onClick={() => setShowBulk(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
