import { apiClient } from "../../shared/api/client";
import type { PageResponse } from "../../shared/api/types";

import type { TeacherDetail, TeacherListItem } from "./types";

const TEACHERS_LIST_CACHE_TTL_MS = 15_000;
const TEACHER_DETAIL_CACHE_TTL_MS = 15_000;

type TeachersFilterParams = {
  status?: "active" | "disabled";
};

type TeachersListCacheEntry = {
  expiresAt: number;
  page?: PageResponse<TeacherListItem>;
  promise?: Promise<PageResponse<TeacherListItem>>;
};

type TeacherDetailCacheEntry = {
  expiresAt: number;
  detail?: TeacherDetail;
  promise?: Promise<TeacherDetail>;
};

const teachersListCache = new Map<string, TeachersListCacheEntry>();
const teacherDetailCache = new Map<string, TeacherDetailCacheEntry>();

function buildTeachersCacheKey(filters: TeachersFilterParams): string {
  return filters.status ?? "all";
}

export function invalidateTeachersCache(): void {
  teachersListCache.clear();
  teacherDetailCache.clear();
}

export async function listTeachers(
  filters: TeachersFilterParams = {}
): Promise<PageResponse<TeacherListItem>> {
  const cacheKey = buildTeachersCacheKey(filters);
  const now = Date.now();
  const cached = teachersListCache.get(cacheKey);

  if (cached?.page && cached.expiresAt > now) {
    return cached.page;
  }
  if (cached?.promise && cached.expiresAt > now) {
    return cached.promise;
  }

  const params = new URLSearchParams({
    limit: "50",
    offset: "0"
  });
  if (filters.status) {
    params.set("status", filters.status);
  }

  const request = apiClient
    .request<PageResponse<TeacherListItem>>(`/admin/teachers?${params.toString()}`)
    .then((page) => {
      teachersListCache.set(cacheKey, {
        page,
        expiresAt: Date.now() + TEACHERS_LIST_CACHE_TTL_MS
      });
      return page;
    })
    .catch((error) => {
      teachersListCache.delete(cacheKey);
      throw error;
    });

  teachersListCache.set(cacheKey, {
    promise: request,
    expiresAt: now + TEACHERS_LIST_CACHE_TTL_MS
  });

  return request;
}

export async function getTeacherDetail(teacherId: string): Promise<TeacherDetail> {
  const now = Date.now();
  const cached = teacherDetailCache.get(teacherId);

  if (cached?.detail && cached.expiresAt > now) {
    return cached.detail;
  }
  if (cached?.promise && cached.expiresAt > now) {
    return cached.promise;
  }

  const request = apiClient
    .request<TeacherDetail>(`/admin/teachers/${teacherId}`)
    .then((detail) => {
      teacherDetailCache.set(teacherId, {
        detail,
        expiresAt: Date.now() + TEACHER_DETAIL_CACHE_TTL_MS
      });
      return detail;
    })
    .catch((error) => {
      teacherDetailCache.delete(teacherId);
      throw error;
    });

  teacherDetailCache.set(teacherId, {
    promise: request,
    expiresAt: now + TEACHER_DETAIL_CACHE_TTL_MS
  });

  return request;
}

export async function disableTeacher(teacherId: string): Promise<TeacherDetail> {
  const detail = await apiClient.request<TeacherDetail>(`/admin/teachers/${teacherId}/disable`, {
    method: "POST"
  });
  teacherDetailCache.set(teacherId, {
    detail,
    expiresAt: Date.now() + TEACHER_DETAIL_CACHE_TTL_MS
  });
  return detail;
}

export async function activateTeacher(teacherId: string): Promise<void> {
  await apiClient.request<unknown>(`/admin/users/${teacherId}/activate`, {
    method: "POST"
  });
}
