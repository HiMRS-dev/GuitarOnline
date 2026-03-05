import { useEffect, useState } from "react";

import { ApiClientError } from "../../shared/api/client";
import { getKpiOverview, getKpiSales } from "../../features/kpi/api";
import type { KpiOverview, KpiSales } from "../../features/kpi/types";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);

function defaultRange() {
  const to = new Date();
  const from = new Date(to);
  from.setDate(to.getDate() - 30);
  return {
    fromUtc: from.toISOString(),
    toUtc: to.toISOString()
  };
}

export function KpiPage() {
  const [overview, setOverview] = useState<KpiOverview | null>(null);
  const [sales, setSales] = useState<KpiSales | null>(null);
  const [fromUtc, setFromUtc] = useState(() => defaultRange().fromUtc.slice(0, 16));
  const [toUtc, setToUtc] = useState(() => defaultRange().toUtc.slice(0, 16));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      getKpiOverview(),
      getKpiSales(new Date(fromUtc).toISOString(), new Date(toUtc).toISOString())
    ])
      .then(([overviewData, salesData]) => {
        setOverview(overviewData);
        setSales(salesData);
      })
      .catch((requestError) => {
        if (
          requestError instanceof ApiClientError &&
          UNAVAILABLE_STATUSES.has(requestError.status)
        ) {
          setUnavailable(true);
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "Failed to load KPI");
      })
      .finally(() => setLoading(false));
  }, [fromUtc, toUtc]);

  if (unavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">KPI</p>
        <h1>Endpoint unavailable</h1>
        <p className="summary">
          KPI page expects <code>GET /admin/kpi/overview</code> and{" "}
          <code>GET /admin/kpi/sales</code>.
        </p>
      </article>
    );
  }

  return (
    <article className="card section-page">
      <p className="eyebrow">KPI</p>
      <h1>KPI Dashboard</h1>

      <div className="kpi-range">
        <label>
          <span>From (UTC)</span>
          <input
            type="datetime-local"
            value={fromUtc}
            onChange={(event) => setFromUtc(event.target.value)}
          />
        </label>
        <label>
          <span>To (UTC)</span>
          <input
            type="datetime-local"
            value={toUtc}
            onChange={(event) => setToUtc(event.target.value)}
          />
        </label>
      </div>

      {loading ? <p className="summary">Loading KPI...</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      {!loading && !error && overview ? (
        <div className="kpi-grid">
          <div className="kpi-tile">
            <h3>Users</h3>
            <p>Total: {overview.users_total}</p>
            <p>Students: {overview.users_students}</p>
            <p>Teachers: {overview.users_teachers}</p>
          </div>
          <div className="kpi-tile">
            <h3>Bookings</h3>
            <p>Total: {overview.bookings_total}</p>
            <p>Confirmed: {overview.bookings_confirmed}</p>
            <p>Canceled: {overview.bookings_canceled}</p>
          </div>
          <div className="kpi-tile">
            <h3>Payments</h3>
            <p>Succeeded: {overview.payments_succeeded}</p>
            <p>Refunded: {overview.payments_refunded}</p>
            <p>Net: {overview.payments_net_amount}</p>
          </div>
          <div className="kpi-tile">
            <h3>Packages</h3>
            <p>Total: {overview.packages_total}</p>
            <p>Active: {overview.packages_active}</p>
            <p>Expired: {overview.packages_expired}</p>
          </div>
        </div>
      ) : null}

      {!loading && !error && sales ? (
        <div className="kpi-sales card">
          <h3>Sales Window</h3>
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
            <strong>Packages created:</strong> {sales.packages_created_total}
          </p>
          <p>
            <strong>Paid conversion:</strong> {sales.packages_created_paid_conversion_rate}
          </p>
        </div>
      ) : null}
    </article>
  );
}
