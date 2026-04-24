const rawApiBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();

export const API_BASE_URL =
  rawApiBaseUrl && rawApiBaseUrl.length > 0
    ? rawApiBaseUrl.replace(/\/+$/, "")
    : "/api/v1";
