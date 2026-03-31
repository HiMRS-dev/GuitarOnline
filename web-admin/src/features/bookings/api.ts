import { apiClient } from "../../shared/api/client";
import type { PageResponse } from "../../shared/api/types";

import type {
  AdminBooking,
  BookingCancelPayload,
  BookingReschedulePayload
} from "./types";

type BookingListParams = {
  teacherId?: string;
  studentId?: string;
  fromUtc?: string;
  toUtc?: string;
  status?: AdminBooking["status"];
  limit?: number;
  offset?: number;
};

export async function listAdminBookings(
  params: BookingListParams
): Promise<PageResponse<AdminBooking>> {
  if (!params.teacherId && !params.studentId) {
    throw new Error("Either teacherId or studentId must be provided");
  }

  const query = new URLSearchParams({
    limit: String(params.limit ?? 100),
    offset: String(params.offset ?? 0)
  });
  if (params.teacherId) {
    query.set("teacher_id", params.teacherId);
  }
  if (params.studentId) {
    query.set("student_id", params.studentId);
  }
  if (params.fromUtc) {
    query.set("from_utc", params.fromUtc);
  }
  if (params.toUtc) {
    query.set("to_utc", params.toUtc);
  }
  if (params.status) {
    query.set("status", params.status);
  }

  return apiClient.request<PageResponse<AdminBooking>>(`/admin/bookings?${query.toString()}`);
}

export async function rescheduleAdminBooking(
  bookingId: string,
  payload: BookingReschedulePayload
): Promise<void> {
  await apiClient.request(`/admin/bookings/${bookingId}/reschedule`, {
    method: "POST",
    body: payload
  });
}

export async function cancelAdminBooking(
  bookingId: string,
  payload: BookingCancelPayload
): Promise<void> {
  await apiClient.request(`/admin/bookings/${bookingId}/cancel`, {
    method: "POST",
    body: payload
  });
}
