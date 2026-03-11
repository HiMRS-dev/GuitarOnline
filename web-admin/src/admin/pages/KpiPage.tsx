import { useEffect, useMemo, useState } from "react";

import { API_BASE_URL } from "../../config";
import { getKpiOverview, getKpiSales } from "../../features/kpi/api";
import type { KpiOverview, KpiSales } from "../../features/kpi/types";
import { ApiClientError, apiClient } from "../../shared/api/client";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);

type ProbeKind = "health" | "ready";
type ProbeStatus = "ok" | "error" | "unknown";

type ProbeSnapshot = {
  kind: ProbeKind;
  status: ProbeStatus;
  httpStatus: number | null;
  detail: string;
  checkedAt: string | null;
};

type DashboardAlert = {
  severity: "info" | "warning" | "critical";
  title: string;
  value: number;
};

type AdminOperationsOverview = {
  generated_at: string;
  max_retries: number;
  outbox_pending: number;
  outbox_failed_retryable: number;
  outbox_failed_dead_letter: number;
  notifications_failed: number;
  stale_booking_holds: number;
  overdue_active_packages: number;
};

const UNKNOWN_HEALTH: ProbeSnapshot = {
  kind: "health",
  status: "unknown",
  httpStatus: null,
  detail: "Не проверено",
  checkedAt: null
};

const UNKNOWN_READY: ProbeSnapshot = {
  kind: "ready",
  status: "unknown",
  httpStatus: null,
  detail: "Не проверено",
  checkedAt: null
};

function defaultRange() {
  const to = new Date();
  const from = new Date(to);
  from.setDate(to.getDate() - 30);
  return {
    fromUtc: from.toISOString(),
    toUtc: to.toISOString()
  };
}

function safeToUtcIso(value: string, fallbackIso: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return fallbackIso;
  }
  return parsed.toISOString();
}

function resolvePlatformUrl(path: "/health" | "/ready"): string {
  try {
    const apiUrl = new URL(API_BASE_URL, window.location.origin);
    return `${apiUrl.origin}${path}`;
  } catch {
    return path;
  }
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(parsed);
}

function probeLabel(kind: ProbeKind): string {
  if (kind === "health") {
    return "Health";
  }
  return "Ready";
}

function probeStatusLabel(status: ProbeStatus): string {
  if (status === "ok") {
    return "OK";
  }
  if (status === "error") {
    return "Ошибка";
  }
  return "Неизвестно";
}

async function fetchProbe(kind: ProbeKind): Promise<ProbeSnapshot> {
  const path = kind === "health" ? "/health" : "/ready";
  const checkedAt = new Date().toISOString();

  try {
    const response = await fetch(resolvePlatformUrl(path), {
      credentials: "include"
    });
    const payload = (await response.json().catch(() => null)) as
      | {
          status?: string;
          detail?: string;
        }
      | null;

    if (response.ok) {
      return {
        kind,
        status: "ok",
        httpStatus: response.status,
        detail: typeof payload?.status === "string" ? payload.status : "ok",
        checkedAt
      };
    }

    return {
      kind,
      status: "error",
      httpStatus: response.status,
      detail: typeof payload?.detail === "string" ? payload.detail : `HTTP ${response.status}`,
      checkedAt
    };
  } catch (probeError) {
    return {
      kind,
      status: "error",
      httpStatus: null,
      detail: probeError instanceof Error ? probeError.message : "Ошибка запроса",
      checkedAt
    };
  }
}

async function getOperationsOverview(): Promise<AdminOperationsOverview> {
  return apiClient.request<AdminOperationsOverview>("/admin/ops/overview?max_retries=5");
}

function buildAlerts(opsOverview: AdminOperationsOverview | null): DashboardAlert[] {
  if (!opsOverview) {
    return [];
  }

  const alerts: DashboardAlert[] = [];
  if (opsOverview.outbox_failed_dead_letter > 0) {
    alerts.push({
      severity: "critical",
      title: "Outbox dead-letter события",
      value: opsOverview.outbox_failed_dead_letter
    });
  }
  if (opsOverview.notifications_failed > 0) {
    alerts.push({
      severity: "warning",
      title: "Ошибки отправки уведомлений",
      value: opsOverview.notifications_failed
    });
  }
  if (opsOverview.stale_booking_holds > 0) {
    alerts.push({
      severity: "warning",
      title: "Зависшие HOLD-бронирования",
      value: opsOverview.stale_booking_holds
    });
  }
  if (opsOverview.overdue_active_packages > 0) {
    alerts.push({
      severity: "warning",
      title: "Просроченные активные пакеты",
      value: opsOverview.overdue_active_packages
    });
  }
  if (opsOverview.outbox_failed_retryable > 0) {
    alerts.push({
      severity: "info",
      title: "Outbox retryable ошибки",
      value: opsOverview.outbox_failed_retryable
    });
  }
  return alerts;
}

export function KpiPage() {
  const [overview, setOverview] = useState<KpiOverview | null>(null);
  const [sales, setSales] = useState<KpiSales | null>(null);
  const [opsOverview, setOpsOverview] = useState<AdminOperationsOverview | null>(null);
  const [healthProbe, setHealthProbe] = useState<ProbeSnapshot>(UNKNOWN_HEALTH);
  const [readyProbe, setReadyProbe] = useState<ProbeSnapshot>(UNKNOWN_READY);
  const [fromUtc, setFromUtc] = useState(() => defaultRange().fromUtc.slice(0, 16));
  const [toUtc, setToUtc] = useState(() => defaultRange().toUtc.slice(0, 16));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [opsError, setOpsError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  const alerts = useMemo(() => buildAlerts(opsOverview), [opsOverview]);

  useEffect(() => {
    let active = true;
    const fallbackRange = defaultRange();
    const fromIso = safeToUtcIso(fromUtc, fallbackRange.fromUtc);
    const toIso = safeToUtcIso(toUtc, fallbackRange.toUtc);

    setLoading(true);
    setError(null);
    setUnavailable(false);

    Promise.all([
      getKpiOverview(),
      getKpiSales(fromIso, toIso),
      fetchProbe("health"),
      fetchProbe("ready"),
      getOperationsOverview()
        .then((data) => ({
          data,
          error: null as string | null
        }))
        .catch((requestError) => ({
          data: null,
          error:
            requestError instanceof Error
              ? requestError.message
              : "Не удалось загрузить операционный обзор"
        }))
    ])
      .then(([overviewData, salesData, healthData, readyData, opsData]) => {
        if (!active) {
          return;
        }
        setOverview(overviewData);
        setSales(salesData);
        setHealthProbe(healthData);
        setReadyProbe(readyData);
        setOpsOverview(opsData.data);
        setOpsError(opsData.error);
      })
      .catch((requestError) => {
        if (!active) {
          return;
        }
        if (
          requestError instanceof ApiClientError &&
          UNAVAILABLE_STATUSES.has(requestError.status)
        ) {
          setUnavailable(true);
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "Не удалось загрузить дашборд");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [fromUtc, toUtc]);

  if (unavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Dashboard</p>
        <h1>Эндпоинты недоступны</h1>
        <p className="summary">
          Для дашборда нужны <code>GET /admin/kpi/overview</code> и <code>GET /admin/kpi/sales</code>.
        </p>
      </article>
    );
  }

  return (
    <article className="card section-page dashboard-page">
      <p className="eyebrow">Dashboard</p>
      <h1>Операционный дашборд</h1>
      <p className="summary">
        Единый экран для состояния платформы: системные пробы, KPI и ключевые сигналы.
      </p>

      <section className="dashboard-status-grid">
        {[healthProbe, readyProbe].map((probe) => (
          <article key={probe.kind} className={`status-card status-${probe.status}`}>
            <h3>{probeLabel(probe.kind)}</h3>
            <p className="status-chip">{probeStatusLabel(probe.status)}</p>
            <p className="summary">HTTP: {probe.httpStatus ?? "-"}</p>
            <p className="summary">Деталь: {probe.detail}</p>
            <p className="summary">Проверено: {formatDateTime(probe.checkedAt)}</p>
          </article>
        ))}
      </section>

      <div className="kpi-range">
        <label>
          <span>Период с (UTC)</span>
          <input
            type="datetime-local"
            value={fromUtc}
            onChange={(event) => setFromUtc(event.target.value)}
          />
        </label>
        <label>
          <span>Период по (UTC)</span>
          <input
            type="datetime-local"
            value={toUtc}
            onChange={(event) => setToUtc(event.target.value)}
          />
        </label>
      </div>

      {loading ? <p className="summary">Загрузка дашборда...</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      {!loading && !error && overview ? (
        <div className="kpi-grid">
          <div className="kpi-tile">
            <h3>Пользователи</h3>
            <p>Всего: {overview.users_total}</p>
            <p>Студентов: {overview.users_students}</p>
            <p>Преподавателей: {overview.users_teachers}</p>
            <p>Админов: {overview.users_admins}</p>
          </div>
          <div className="kpi-tile">
            <h3>Бронирования</h3>
            <p>Всего: {overview.bookings_total}</p>
            <p>HOLD: {overview.bookings_hold}</p>
            <p>Подтверждено: {overview.bookings_confirmed}</p>
            <p>Отменено: {overview.bookings_canceled}</p>
          </div>
          <div className="kpi-tile">
            <h3>Платежи</h3>
            <p>Успешных: {overview.payments_succeeded}</p>
            <p>Возвратов: {overview.payments_refunded}</p>
            <p>Net: {overview.payments_net_amount}</p>
          </div>
          <div className="kpi-tile">
            <h3>Пакеты</h3>
            <p>Всего: {overview.packages_total}</p>
            <p>Активных: {overview.packages_active}</p>
            <p>Истекших: {overview.packages_expired}</p>
            <p>Исчерпанных: {overview.packages_depleted}</p>
          </div>
        </div>
      ) : null}

      {!loading && !error && sales ? (
        <div className="kpi-sales card">
          <h3>Продажи за период</h3>
          <p>
            <strong>Net amount:</strong> {sales.payments_net_amount}
          </p>
          <p>
            <strong>Succeeded amount:</strong> {sales.payments_succeeded_amount}
          </p>
          <p>
            <strong>Refunded amount:</strong> {sales.payments_refunded_amount}
          </p>
          <p>
            <strong>Создано пакетов:</strong> {sales.packages_created_total}
          </p>
          <p>
            <strong>Paid conversion:</strong> {sales.packages_created_paid_conversion_rate}
          </p>
        </div>
      ) : null}

      <section className="dashboard-ops card">
        <h3>Операционный обзор</h3>
        {opsError ? <p className="error-text">{opsError}</p> : null}
        {!opsError && opsOverview ? (
          <div className="ops-grid">
            <p>
              <strong>Outbox pending:</strong> {opsOverview.outbox_pending}
            </p>
            <p>
              <strong>Outbox retryable failed:</strong> {opsOverview.outbox_failed_retryable}
            </p>
            <p>
              <strong>Outbox dead-letter:</strong> {opsOverview.outbox_failed_dead_letter}
            </p>
            <p>
              <strong>Ошибки уведомлений:</strong> {opsOverview.notifications_failed}
            </p>
            <p>
              <strong>Зависшие HOLD:</strong> {opsOverview.stale_booking_holds}
            </p>
            <p>
              <strong>Просроченные активные пакеты:</strong> {opsOverview.overdue_active_packages}
            </p>
            <p>
              <strong>Снимок:</strong> {formatDateTime(opsOverview.generated_at)}
            </p>
          </div>
        ) : null}
        {!opsError && !opsOverview ? (
          <p className="summary">Операционные метрики пока недоступны.</p>
        ) : null}
      </section>

      <section className="dashboard-alerts card">
        <h3>Ключевые сигналы</h3>
        {!opsOverview && !opsError ? <p className="summary">Ожидание данных...</p> : null}
        {opsOverview && alerts.length === 0 ? (
          <p className="success-text">Критичных сигналов не обнаружено.</p>
        ) : null}
        {alerts.length > 0 ? (
          <ul className="alerts-list">
            {alerts.map((alert) => (
              <li key={`${alert.severity}-${alert.title}`} className={`alert-item ${alert.severity}`}>
                <strong>{alert.title}:</strong> {alert.value}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </article>
  );
}
