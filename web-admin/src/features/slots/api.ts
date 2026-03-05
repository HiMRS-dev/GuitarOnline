import { apiClient } from "../../shared/api/client";
import type { PageResponse } from "../../shared/api/types";

import type {
  AdminSlot,
  SlotBlockPayload,
  SlotBulkCreatePayload,
  SlotCreatePayload
} from "./types";

type SlotListParams = {
  teacherId: string;
  fromUtc: string;
  toUtc: string;
};

export async function listAdminSlots(params: SlotListParams): Promise<PageResponse<AdminSlot>> {
  const query = new URLSearchParams({
    teacher_id: params.teacherId,
    from_utc: params.fromUtc,
    to_utc: params.toUtc,
    limit: "300",
    offset: "0"
  });
  return apiClient.request<PageResponse<AdminSlot>>(`/admin/slots?${query.toString()}`);
}

export async function createAdminSlot(payload: SlotCreatePayload): Promise<void> {
  await apiClient.request("/admin/slots", {
    method: "POST",
    body: payload
  });
}

export async function blockAdminSlot(slotId: string, payload: SlotBlockPayload): Promise<void> {
  await apiClient.request(`/admin/slots/${slotId}/block`, {
    method: "POST",
    body: payload
  });
}

export async function bulkCreateAdminSlots(payload: SlotBulkCreatePayload): Promise<void> {
  await apiClient.request("/admin/slots/bulk-create", {
    method: "POST",
    body: payload
  });
}
