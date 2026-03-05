import { apiClient } from "../../shared/api/client";
import type { PageResponse } from "../../shared/api/types";

import type { TeacherDetail, TeacherListItem } from "./types";

type TeachersFilterParams = {
  status?: "pending" | "verified" | "disabled";
};

export async function listTeachers(
  filters: TeachersFilterParams = {}
): Promise<PageResponse<TeacherListItem>> {
  const params = new URLSearchParams({
    limit: "50",
    offset: "0"
  });
  if (filters.status) {
    params.set("status", filters.status);
  }
  return apiClient.request<PageResponse<TeacherListItem>>(`/admin/teachers?${params.toString()}`);
}

export async function getTeacherDetail(teacherId: string): Promise<TeacherDetail> {
  return apiClient.request<TeacherDetail>(`/admin/teachers/${teacherId}`);
}
