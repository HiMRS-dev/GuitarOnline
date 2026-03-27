import { apiClient } from "../../shared/api/client";

import type { KpiOverview, KpiSales } from "./types";

const KPI_OVERVIEW_CACHE_TTL_MS = 15_000;

let cachedOverview: KpiOverview | null = null;
let cachedOverviewExpiresAt = 0;
let cachedOverviewPromise: Promise<KpiOverview> | null = null;

export function invalidateKpiOverviewCache(): void {
  cachedOverview = null;
  cachedOverviewExpiresAt = 0;
  cachedOverviewPromise = null;
}

export async function getKpiOverview(): Promise<KpiOverview> {
  const now = Date.now();

  if (cachedOverview !== null && cachedOverviewExpiresAt > now) {
    return cachedOverview;
  }
  if (cachedOverviewPromise !== null && cachedOverviewExpiresAt > now) {
    return cachedOverviewPromise;
  }

  cachedOverviewPromise = apiClient
    .request<KpiOverview>("/admin/kpi/overview")
    .then((overview) => {
      cachedOverview = overview;
      cachedOverviewExpiresAt = Date.now() + KPI_OVERVIEW_CACHE_TTL_MS;
      cachedOverviewPromise = null;
      return overview;
    })
    .catch((error) => {
      cachedOverviewPromise = null;
      cachedOverviewExpiresAt = 0;
      throw error;
    });

  cachedOverviewExpiresAt = now + KPI_OVERVIEW_CACHE_TTL_MS;
  return cachedOverviewPromise;
}

export async function getKpiSales(fromUtc: string, toUtc: string): Promise<KpiSales> {
  const query = new URLSearchParams({
    from_utc: fromUtc,
    to_utc: toUtc
  });
  return apiClient.request<KpiSales>(`/admin/kpi/sales?${query.toString()}`);
}
