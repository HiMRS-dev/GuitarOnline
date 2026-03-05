import { apiClient } from "../../shared/api/client";
import type { PageResponse } from "../../shared/api/types";

import type { AdminPackage } from "./types";

type PackageListParams = {
  studentId?: string;
  status?: string;
};

export async function listAdminPackages(
  params: PackageListParams = {}
): Promise<PageResponse<AdminPackage>> {
  const query = new URLSearchParams({
    limit: "100",
    offset: "0"
  });
  if (params.studentId) {
    query.set("student_id", params.studentId);
  }
  if (params.status) {
    query.set("status", params.status);
  }
  return apiClient.request<PageResponse<AdminPackage>>(`/admin/packages?${query.toString()}`);
}
