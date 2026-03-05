import { apiClient } from "../../shared/api/client";

import type { KpiOverview, KpiSales } from "./types";

export async function getKpiOverview(): Promise<KpiOverview> {
  return apiClient.request<KpiOverview>("/admin/kpi/overview");
}

export async function getKpiSales(fromUtc: string, toUtc: string): Promise<KpiSales> {
  const query = new URLSearchParams({
    from_utc: fromUtc,
    to_utc: toUtc
  });
  return apiClient.request<KpiSales>(`/admin/kpi/sales?${query.toString()}`);
}
