import type {
  DataProvider,
  GetListResult,
  GetManyReferenceResult,
  GetManyResult,
  GetOneResult,
  RaRecord
} from "react-admin";

import { apiClient } from "../shared/api/client";
import type { PageResponse } from "../shared/api/types";

type TeacherApiRecord = {
  teacher_id: string;
  profile_id: string;
  email: string;
  full_name: string;
  display_name: string;
  timezone: string;
  status: string;
  is_active: boolean;
  tags: string[];
  created_at_utc: string;
  updated_at_utc: string;
  bio?: string;
  experience_years?: number;
};

export type TeacherRaRecord = TeacherApiRecord & {
  id: string;
};

type UserApiRecord = {
  user_id: string;
  email: string;
  full_name: string;
  timezone: string;
  role: string;
  is_active: boolean;
  teacher_profile_display_name: string | null;
  created_at_utc: string;
  updated_at_utc: string;
};

export type StudentRaRecord = UserApiRecord & {
  id: string;
};

function toTeacherRecord(record: TeacherApiRecord): TeacherRaRecord {
  return {
    ...record,
    id: record.teacher_id
  };
}

function toStudentRecord(record: UserApiRecord): StudentRaRecord {
  return {
    ...record,
    id: record.user_id
  };
}

function toStringFilterValue(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

type TeachersListQueryParams = {
  pagination?: {
    page?: number;
    perPage?: number;
  };
  filter?: Record<string, unknown>;
};

type StudentsListQueryParams = {
  pagination?: {
    page?: number;
    perPage?: number;
  };
  filter?: Record<string, unknown>;
};

type TeacherGetOneParams = {
  id: string | number;
};

function buildTeachersListQuery(params: TeachersListQueryParams): string {
  const page = params.pagination?.page ?? 1;
  const perPage = params.pagination?.perPage ?? 20;
  const offset = (page - 1) * perPage;

  const query = new URLSearchParams({
    limit: String(perPage),
    offset: String(offset)
  });

  const status = toStringFilterValue(params.filter?.status);
  if (status === "active" || status === "disabled") {
    query.set("status", status);
  }

  const searchQuery = toStringFilterValue(params.filter?.q);
  if (searchQuery !== null) {
    query.set("q", searchQuery);
  }

  const tag = toStringFilterValue(params.filter?.tag);
  if (tag !== null) {
    query.set("tag", tag);
  }

  return query.toString();
}

function buildStudentsListQuery(params: StudentsListQueryParams): string {
  const page = params.pagination?.page ?? 1;
  const perPage = params.pagination?.perPage ?? 20;
  const offset = (page - 1) * perPage;

  const query = new URLSearchParams({
    role: "student",
    limit: String(perPage),
    offset: String(offset)
  });

  const searchQuery = toStringFilterValue(params.filter?.q);
  if (searchQuery !== null) {
    query.set("q", searchQuery);
  }

  if (params.filter?.is_active === true) {
    query.set("is_active", "true");
  }
  if (params.filter?.is_active === false) {
    query.set("is_active", "false");
  }

  return query.toString();
}

function unsupportedResourceError(resource: string): Error {
  return new Error(
    `[ADM-04] Resource "${resource}" is not connected yet. This will be covered in ADM-05.`
  );
}

async function getTeachersList(params: TeachersListQueryParams) {
  const query = buildTeachersListQuery(params);
  const response = await apiClient.request<PageResponse<TeacherApiRecord>>(
    `/admin/teachers?${query}`
  );
  return {
    data: response.items.map(toTeacherRecord),
    total: response.total
  };
}

async function getStudentsList(params: StudentsListQueryParams) {
  const query = buildStudentsListQuery(params);
  const response = await apiClient.request<PageResponse<UserApiRecord>>(`/admin/users?${query}`);
  return {
    data: response.items.map(toStudentRecord),
    total: response.total
  };
}

async function getTeacherById(params: TeacherGetOneParams) {
  const response = await apiClient.request<TeacherApiRecord>(`/admin/teachers/${params.id}`);
  return { data: toTeacherRecord(response) };
}

function asGetListResult<RecordType extends RaRecord>(
  result: GetListResult<TeacherRaRecord>
): GetListResult<RecordType> {
  return result as unknown as GetListResult<RecordType>;
}

function asGetOneResult<RecordType extends RaRecord>(
  result: GetOneResult<TeacherRaRecord>
): GetOneResult<RecordType> {
  return result as unknown as GetOneResult<RecordType>;
}

function asGetManyResult<RecordType extends RaRecord>(
  result: GetManyResult<TeacherRaRecord>
): GetManyResult<RecordType> {
  return result as unknown as GetManyResult<RecordType>;
}

function asGetManyReferenceResult<RecordType extends RaRecord>(
  result: GetManyReferenceResult<TeacherRaRecord>
): GetManyReferenceResult<RecordType> {
  return result as unknown as GetManyReferenceResult<RecordType>;
}

function asStudentGetListResult<RecordType extends RaRecord>(
  result: GetListResult<StudentRaRecord>
): GetListResult<RecordType> {
  return result as unknown as GetListResult<RecordType>;
}

function asStudentGetManyResult<RecordType extends RaRecord>(
  result: GetManyResult<StudentRaRecord>
): GetManyResult<RecordType> {
  return result as unknown as GetManyResult<RecordType>;
}

function asStudentGetManyReferenceResult<RecordType extends RaRecord>(
  result: GetManyReferenceResult<StudentRaRecord>
): GetManyReferenceResult<RecordType> {
  return result as unknown as GetManyReferenceResult<RecordType>;
}

export const adminPlatformDataProvider: DataProvider = {
  async getList(resource, params) {
    if (resource === "teachers") {
      return asGetListResult(await getTeachersList(params));
    }
    if (resource === "students") {
      return asStudentGetListResult(await getStudentsList(params));
    }
    throw unsupportedResourceError(resource);
  },
  async getOne(resource, params) {
    if (resource === "teachers") {
      return asGetOneResult(await getTeacherById(params));
    }
    throw unsupportedResourceError(resource);
  },
  async getMany(resource, params) {
    if (resource === "teachers") {
      const rows = await Promise.all(
        params.ids.map(async (id) => {
          const response = await apiClient.request<TeacherApiRecord>(`/admin/teachers/${id}`);
          return toTeacherRecord(response);
        })
      );
      return asGetManyResult({ data: rows });
    }
    if (resource === "students") {
      const response = await apiClient.request<PageResponse<UserApiRecord>>(
        `/admin/users?role=student&limit=100&offset=0`
      );
      const idSet = new Set(params.ids.map((id) => String(id)));
      const rows = response.items
        .filter((item) => idSet.has(item.user_id))
        .map(toStudentRecord);
      return asStudentGetManyResult({ data: rows });
    }
    throw unsupportedResourceError(resource);
  },
  async getManyReference(resource, params) {
    if (resource === "teachers") {
      return asGetManyReferenceResult(await getTeachersList(params));
    }
    if (resource === "students") {
      return asStudentGetManyReferenceResult(await getStudentsList(params));
    }
    throw unsupportedResourceError(resource);
  },
  async update(resource) {
    throw unsupportedResourceError(resource);
  },
  async updateMany(resource) {
    throw unsupportedResourceError(resource);
  },
  async create(resource) {
    throw unsupportedResourceError(resource);
  },
  async delete(resource) {
    throw unsupportedResourceError(resource);
  },
  async deleteMany(resource) {
    throw unsupportedResourceError(resource);
  }
};
