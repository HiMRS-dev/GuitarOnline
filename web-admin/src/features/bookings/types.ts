export type AdminBooking = {
  booking_id: string;
  slot_id: string;
  student_id: string;
  teacher_id: string;
  package_id: string | null;
  status: "hold" | "confirmed" | "canceled" | "expired";
  slot_start_at_utc: string;
  slot_end_at_utc: string;
  hold_expires_at_utc: string | null;
  confirmed_at_utc: string | null;
  canceled_at_utc: string | null;
  cancellation_reason: string | null;
  refund_returned: boolean;
  rescheduled_from_booking_id: string | null;
  created_at_utc: string;
  updated_at_utc: string;
};

export type BookingReschedulePayload = {
  new_slot_id: string;
  reason: string;
};
