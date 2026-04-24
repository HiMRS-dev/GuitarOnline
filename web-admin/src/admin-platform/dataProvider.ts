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

function toTeacherRecord(record: TeacherApiRecord): TeacherRaRecord {
  return {
    ...record,
    id: record.teacher_id
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

export const adminPlatformDataProvider: DataProvider = {
  async getList(resource, params) {
    if (resource === "teachers") {
      return asGetListResult(await getTeachersList(params));
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
    throw unsupportedResourceError(resource);
  },
  async getManyReference(resource, params) {
    if (resource === "teachers") {
      return asGetManyReferenceResult(await getTeachersList(params));
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
