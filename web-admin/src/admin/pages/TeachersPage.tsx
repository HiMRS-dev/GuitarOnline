import { useEffect, useMemo, useState } from "react";

import { ApiClientError } from "../../shared/api/client";
import { getTeacherDetail, listTeachers } from "../../features/teachers/api";
import type { TeacherDetail, TeacherListItem } from "../../features/teachers/types";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);

export function TeachersPage() {
  const [teachers, setTeachers] = useState<TeacherListItem[]>([]);
  const [selectedTeacherId, setSelectedTeacherId] = useState<string | null>(null);
  const [teacherDetail, setTeacherDetail] = useState<TeacherDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    listTeachers()
      .then((page) => {
        if (!active) {
          return;
        }
        setTeachers(page.items);
        setSelectedTeacherId(page.items[0]?.teacher_id ?? null);
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
        setError(requestError instanceof Error ? requestError.message : "Failed to load teachers");
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
    if (!selectedTeacherId || unavailable) {
      setTeacherDetail(null);
      return;
    }

    let active = true;
    setDetailError(null);
    getTeacherDetail(selectedTeacherId)
      .then((detail) => {
        if (active) {
          setTeacherDetail(detail);
        }
      })
      .catch((requestError) => {
        if (active) {
          setDetailError(
            requestError instanceof Error ? requestError.message : "Failed to load detail"
          );
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

  if (unavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Teachers</p>
        <h1>Endpoint unavailable</h1>
        <p className="summary">
          Teacher admin endpoints are not available yet. Expected endpoints:
          <code>GET /admin/teachers</code> and <code>GET /admin/teachers/{`{id}`}</code>.
        </p>
      </article>
    );
  }

  if (loading) {
    return (
      <article className="card section-page">
        <h1>Teachers</h1>
        <p className="summary">Loading teacher list...</p>
      </article>
    );
  }

  if (error) {
    return (
      <article className="card section-page">
        <h1>Teachers</h1>
        <p className="error-text">{error}</p>
      </article>
    );
  }

  return (
    <section className="teachers-grid">
      <article className="card">
        <p className="eyebrow">Teachers</p>
        <h1>Teacher List</h1>
        {teachers.length === 0 ? (
          <p className="summary">No teachers found.</p>
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
                  {teacher.status} {teacher.verified ? "• verified" : "• pending"}
                </span>
              </button>
            ))}
          </div>
        )}
      </article>

      <article className="card">
        <p className="eyebrow">Teacher Detail</p>
        {selectedTeacher ? <h1>{selectedTeacher.display_name}</h1> : <h1>No selection</h1>}
        {detailError ? <p className="error-text">{detailError}</p> : null}
        {teacherDetail ? (
          <div className="teacher-detail">
            <p>
              <strong>Status:</strong> {teacherDetail.status}
            </p>
            <p>
              <strong>Experience:</strong> {teacherDetail.experience_years} years
            </p>
            <p>
              <strong>Email:</strong> {teacherDetail.email}
            </p>
            <p>
              <strong>Tags:</strong>{" "}
              {teacherDetail.tags.length ? teacherDetail.tags.join(", ") : "none"}
            </p>
            <p>
              <strong>Bio:</strong> {teacherDetail.bio}
            </p>
          </div>
        ) : (
          <p className="summary">Select teacher to view detail.</p>
        )}
      </article>
    </section>
  );
}
