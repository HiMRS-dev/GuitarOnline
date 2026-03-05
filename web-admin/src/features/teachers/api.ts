import { apiClient } from "../../shared/api/client";
import type { PageResponse } from "../../shared/api/types";

import type { TeacherDetail, TeacherListItem } from "./types";

export async function listTeachers(): Promise<PageResponse<TeacherListItem>> {
  return apiClient.request<PageResponse<TeacherListItem>>("/admin/teachers?limit=20&offset=0");
}

export async function getTeacherDetail(teacherId: string): Promise<TeacherDetail> {
  return apiClient.request<TeacherDetail>(`/admin/teachers/${teacherId}`);
}
