# Admin API Contract (v1)

This document defines the baseline response DTOs for the admin frontend.

## Contract Rules

- All datetime fields in admin contracts use UTC and end with `_at_utc`.
- Datetime format: ISO8601 with timezone, for example `2026-03-04T12:30:00+00:00`.
- Error format is unified for all endpoints:
  - `{ "error": { "code": "...", "message": "...", "details": {...} } }`

## DTOs

- `Teacher`: [`AdminTeacherDTO`](../app/modules/admin/contracts.py)
- `Slot`: [`AdminSlotDTO`](../app/modules/admin/contracts.py)
- `Booking`: [`AdminBookingDTO`](../app/modules/admin/contracts.py)
- `Package`: [`AdminPackageDTO`](../app/modules/admin/contracts.py)
- `Payment`: [`AdminPaymentDTO`](../app/modules/admin/contracts.py)
- `Student`: [`AdminStudentDTO`](../app/modules/admin/contracts.py)
- `Lesson`: [`AdminLessonDTO`](../app/modules/admin/contracts.py)

## Field Migration Map (Legacy -> Admin)

| Legacy field | Admin contract field |
|---|---|
| `created_at` | `created_at_utc` |
| `updated_at` | `updated_at_utc` |
| `start_at` | `start_at_utc` |
| `end_at` | `end_at_utc` |
| `expires_at` | `expires_at_utc` |
| `hold_expires_at` | `hold_expires_at_utc` |
| `confirmed_at` | `confirmed_at_utc` |
| `canceled_at` | `canceled_at_utc` |
| `paid_at` | `paid_at_utc` |
| `scheduled_start_at` | `scheduled_start_at_utc` |
| `scheduled_end_at` | `scheduled_end_at_utc` |

## Response Examples

### Teacher

```json
{
  "id": "6bd7d579-4d78-4b06-8f3f-8ad62020f0c0",
  "user_id": "84d1ecf5-0d3d-41b7-9ebf-f59b97f15b53",
  "email": "teacher@example.com",
  "display_name": "Alice Blues",
  "bio": "Fingerstyle teacher",
  "experience_years": 8,
  "status": "active",
  "created_at_utc": "2026-03-04T09:30:00+00:00",
  "updated_at_utc": "2026-03-04T10:00:00+00:00"
}
```

### Slot

```json
{
  "id": "d8f2768a-4480-4800-88bf-2f36d5d8f6f6",
  "teacher_id": "84d1ecf5-0d3d-41b7-9ebf-f59b97f15b53",
  "created_by_admin_id": "c4ea1016-8586-4602-9fbe-c1100d2057a1",
  "start_at_utc": "2026-03-07T12:00:00+00:00",
  "end_at_utc": "2026-03-07T13:00:00+00:00",
  "status": "open",
  "created_at_utc": "2026-03-04T10:20:00+00:00",
  "updated_at_utc": "2026-03-04T10:20:00+00:00"
}
```

### Booking

```json
{
  "id": "6b6a1681-f4d1-47fc-b6de-d4f4f657f57d",
  "slot_id": "d8f2768a-4480-4800-88bf-2f36d5d8f6f6",
  "student_id": "a46d9185-3369-4f6f-9506-5e01d5fdbd26",
  "teacher_id": "84d1ecf5-0d3d-41b7-9ebf-f59b97f15b53",
  "package_id": "9f2b8758-beb8-4c8b-bd23-3615e7c05a23",
  "status": "confirmed",
  "hold_expires_at_utc": null,
  "confirmed_at_utc": "2026-03-04T10:25:00+00:00",
  "canceled_at_utc": null,
  "cancellation_reason": null,
  "refund_returned": false,
  "rescheduled_from_booking_id": null,
  "created_at_utc": "2026-03-04T10:15:00+00:00",
  "updated_at_utc": "2026-03-04T10:25:00+00:00"
}
```

### Package

```json
{
  "id": "9f2b8758-beb8-4c8b-bd23-3615e7c05a23",
  "student_id": "a46d9185-3369-4f6f-9506-5e01d5fdbd26",
  "lessons_total": 12,
  "lessons_left": 11,
  "expires_at_utc": "2026-06-01T00:00:00+00:00",
  "status": "active",
  "created_at_utc": "2026-03-01T00:00:00+00:00",
  "updated_at_utc": "2026-03-04T10:25:00+00:00"
}
```

### Student

```json
{
  "id": "a46d9185-3369-4f6f-9506-5e01d5fdbd26",
  "email": "student@example.com",
  "timezone": "UTC",
  "is_active": true,
  "role": "student",
  "created_at_utc": "2026-02-20T12:00:00+00:00",
  "updated_at_utc": "2026-03-04T08:00:00+00:00"
}
```

### Lesson

```json
{
  "id": "4bb0dbcc-7db0-4d7f-9849-14757f27de2d",
  "booking_id": "6b6a1681-f4d1-47fc-b6de-d4f4f657f57d",
  "student_id": "a46d9185-3369-4f6f-9506-5e01d5fdbd26",
  "teacher_id": "84d1ecf5-0d3d-41b7-9ebf-f59b97f15b53",
  "scheduled_start_at_utc": "2026-03-07T12:00:00+00:00",
  "scheduled_end_at_utc": "2026-03-07T13:00:00+00:00",
  "status": "scheduled",
  "topic": "Chord transitions",
  "notes": "Focus on tempo stability",
  "created_at_utc": "2026-03-04T10:25:00+00:00",
  "updated_at_utc": "2026-03-04T10:25:00+00:00"
}
```
