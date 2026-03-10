import { API_BASE_URL } from "../../config";
import {
  clearAccessSession,
  loadAccessSession,
  saveTokenPair
} from "../../features/auth/storage";
import type { TokenPair } from "../../features/auth/types";

type ApiRequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  auth?: boolean;
  signal?: AbortSignal;
  retryOnUnauthorized?: boolean;
};

type ErrorPayload = {
  error?: {
    message?: string;
    details?: {
      detail?: string | { msg?: string };
      errors?: Array<{ message?: string }>;
    } | null;
  };
  detail?: string | { msg?: string };
};

export class ApiClientError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function normalizeBackendError(status: number, payload: ErrorPayload | null): ApiClientError {
  const backendMessage = payload?.error?.message;
  if (typeof backendMessage === "string" && backendMessage.trim()) {
    return new ApiClientError(backendMessage, status);
  }

  const backendDetail = payload?.error?.details?.detail;
  if (typeof backendDetail === "string" && backendDetail.trim()) {
    return new ApiClientError(backendDetail, status);
  }
  if (
    backendDetail &&
    typeof backendDetail === "object" &&
    typeof backendDetail.msg === "string" &&
    backendDetail.msg.trim()
  ) {
    return new ApiClientError(backendDetail.msg, status);
  }

  const firstValidationMessage = payload?.error?.details?.errors?.[0]?.message;
  if (typeof firstValidationMessage === "string" && firstValidationMessage.trim()) {
    return new ApiClientError(firstValidationMessage, status);
  }

  const detail = payload?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return new ApiClientError(detail, status);
  }
  if (detail && typeof detail === "object" && typeof detail.msg === "string" && detail.msg.trim()) {
    return new ApiClientError(detail.msg, status);
  }
  return new ApiClientError(`Request failed with status ${status}`, status);
}

export class ApiClient {
  async request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
    const shouldUseAuth = options.auth ?? true;
    const retryOnUnauthorized = options.retryOnUnauthorized ?? true;

    const headers: Record<string, string> = {
      ...(options.headers ?? {})
    };
    if (options.body !== undefined && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    if (shouldUseAuth) {
      const session = loadAccessSession();
      if (session) {
        headers.Authorization = `Bearer ${session.access_token}`;
      }
    }

    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
      credentials: "include"
    });

    if (response.status === 401 && shouldUseAuth && retryOnUnauthorized) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) {
        return this.request<T>(path, {
          ...options,
          retryOnUnauthorized: false
        });
      }
      clearAccessSession();
    }

    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as ErrorPayload | null;
      throw normalizeBackendError(response.status, payload);
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }

  private async refreshAccessToken(): Promise<boolean> {
    const response = await fetch(`${API_BASE_URL}/identity/auth/refresh`, {
      method: "POST",
      credentials: "include"
    });
    if (!response.ok) {
      return false;
    }

    const refreshed = (await response.json()) as TokenPair;
    if (!refreshed.access_token || !refreshed.token_type) {
      return false;
    }
    saveTokenPair(refreshed);
    return true;
  }
}

export const apiClient = new ApiClient();
