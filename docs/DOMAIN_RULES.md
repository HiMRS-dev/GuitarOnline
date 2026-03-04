# Domain Rules (v1)

## Slot, Booking, Lesson Source of Truth

- `Slot` is teacher availability.
  - A slot is free only when no active booking owns it.
  - Slot statuses reflect scheduling state (`open`, `hold`, `booked`, `canceled`).
- `Booking` is a reservation over one slot.
  - `hold` means temporary reservation with expiration.
  - `confirmed` means reservation is finalized and linked to package consumption.
  - `canceled` and `expired` are terminal states.
- `Lesson` is the fact entity for the class lifecycle.
  - Lesson is created from confirmed booking.
  - Lesson keeps teaching metadata and completion status.

## Consistency Rules

- One slot can have at most one booking (`bookings.slot_id` is unique).
- One booking can have at most one lesson (`lessons.booking_id` is unique).
- Booking confirmation is the trigger point to ensure lesson existence.
- Booking cancel/reschedule updates linked lesson state to avoid orphans.

## Time Rules

- All business datetimes are normalized to UTC on write.
- Admin contracts expose datetime fields as `*_at_utc`.

## Refund Policy

- Cancellation more than 24 hours before lesson start can return one lesson.
- Cancellation within 24 hours does not return lesson balance.

## Role Rules

- `/admin/**` endpoints are admin-only.
- Teacher profile endpoints require `teacher` role or explicit `admin` override.
- Student booking hold endpoint is student-only.
