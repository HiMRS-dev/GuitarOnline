export type AdminSlot = {
  slot_id: string;
  teacher_id: string;
  created_by_admin_id: string;
  start_at_utc: string;
  end_at_utc: string;
  slot_status: "open" | "hold" | "booked" | "canceled" | "blocked";
  booking_id: string | null;
  booking_status: "hold" | "confirmed" | "canceled" | "expired" | null;
  aggregated_booking_status: "open" | "held" | "confirmed";
  created_at_utc: string;
  updated_at_utc: string;
};

export type SlotCreatePayload = {
  teacher_id: string;
  start_at_utc: string;
  end_at_utc: string;
};

export type SlotBlockPayload = {
  reason: string;
};

export type SlotBulkCreatePayload = {
  teacher_id: string;
  date_from_utc: string;
  date_to_utc: string;
  weekdays: number[];
  start_time_utc: string;
  end_time_utc: string;
  slot_duration_minutes: number;
  exclude_dates: string[];
  exclude_time_ranges: { start_time_utc: string; end_time_utc: string }[];
};
