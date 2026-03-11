import { apiClient } from "../../shared/api/client";
import type { PageResponse } from "../../shared/api/types";

import type {
  AdminBooking,
  BookingCancelPayload,
  BookingReschedulePayload
} from "./types";

type BookingListParams = {
  teacherId: string;
  fromUtc: string;
  toUtc: string;
};

export async function listAdminBookings(
  params: BookingListParams
): Promise<PageResponse<AdminBooking>> {
  const query = new URLSearchParams({
    teacher_id: params.teacherId,
    from_utc: params.fromUtc,
    to_utc: params.toUtc,
    limit: "100",
    offset: "0"
  });
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
