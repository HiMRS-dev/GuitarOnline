import { useEffect, useState } from "react";

import { ApiClientError } from "../../shared/api/client";
import { listAdminPackages } from "../../features/packages/api";
import type { AdminPackage } from "../../features/packages/types";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);

const PACKAGE_STATUSES = ["", "active", "expired", "depleted", "canceled"];

export function PackagesPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const [packages, setPackages] = useState<AdminPackage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    listAdminPackages({
      status: statusFilter || undefined
    })
      .then((page) => {
        setPackages(page.items);
      })
      .catch((requestError) => {
        if (
          requestError instanceof ApiClientError &&
          UNAVAILABLE_STATUSES.has(requestError.status)
        ) {
          setUnavailable(true);
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "Failed to load packages");
      })
      .finally(() => setLoading(false));
  }, [statusFilter]);

  if (unavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Packages</p>
        <h1>Endpoint unavailable</h1>
        <p className="summary">
          Package list UI requires <code>GET /admin/packages</code>.
        </p>
      </article>
    );
  }

  return (
    <article className="card section-page">
      <p className="eyebrow">Packages</p>
      <h1>Packages</h1>

      <label className="inline-filter">
        <span>Status</span>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          {PACKAGE_STATUSES.map((status) => (
            <option key={status || "all"} value={status}>
              {status || "all"}
            </option>
          ))}
        </select>
      </label>

      {loading ? <p className="summary">Loading packages...</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      {!loading && !error ? (
        packages.length ? (
          <div className="bookings-table-wrap">
            <table className="bookings-table">
              <thead>
                <tr>
                  <th>Package</th>
                  <th>Student</th>
                  <th>Status</th>
                  <th>Left</th>
                  <th>Reserved</th>
                  <th>Price</th>
                  <th>Expires</th>
                </tr>
              </thead>
              <tbody>
                {packages.map((pkg) => (
                  <tr key={pkg.package_id}>
                    <td>{pkg.package_id.slice(0, 8)}</td>
                    <td>{pkg.student_id.slice(0, 8)}</td>
                    <td>{pkg.status}</td>
                    <td>{pkg.lessons_left}</td>
                    <td>{pkg.lessons_reserved}</td>
                    <td>
                      {pkg.price_amount
                        ? `${pkg.price_amount} ${pkg.price_currency ?? ""}`
                        : "-"}
                    </td>
                    <td>{new Date(pkg.expires_at_utc).toISOString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="summary">No packages found for selected filter.</p>
        )
      ) : null}
    </article>
  );
}
