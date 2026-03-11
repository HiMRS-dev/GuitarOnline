import { FormEvent, useCallback, useEffect, useState } from "react";

import { ApiClientError } from "../../shared/api/client";
import { createAdminPackage, listAdminPackages } from "../../features/packages/api";
import type { AdminPackage } from "../../features/packages/types";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);

const PACKAGE_STATUSES = ["", "active", "expired", "depleted", "canceled"];

export function PackagesPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const [packages, setPackages] = useState<AdminPackage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);
  const [createPending, setCreatePending] = useState(false);
  const [unavailable, setUnavailable] = useState(false);

  const [studentId, setStudentId] = useState("");
  const [lessonsTotal, setLessonsTotal] = useState("8");
  const [expiresAtUtc, setExpiresAtUtc] = useState("");
  const [priceAmount, setPriceAmount] = useState("149.00");
  const [priceCurrency, setPriceCurrency] = useState("USD");

  const loadPackages = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await listAdminPackages({
        status: statusFilter || undefined
      });
      setPackages(page.items);
    } catch (requestError) {
      if (requestError instanceof ApiClientError && UNAVAILABLE_STATUSES.has(requestError.status)) {
        setUnavailable(true);
        return;
      }
      setError(requestError instanceof Error ? requestError.message : "Failed to load packages");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    void loadPackages();
  }, [loadPackages]);

  async function handleCreatePackage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    setCreateSuccess(null);

    const parsedLessonsTotal = Number(lessonsTotal);
    const parsedExpiresAt = new Date(expiresAtUtc);
    if (!studentId.trim()) {
      setCreateError("Student ID is required.");
      return;
    }
    if (!Number.isInteger(parsedLessonsTotal) || parsedLessonsTotal <= 0) {
      setCreateError("Lessons total must be a positive integer.");
      return;
    }
    if (!expiresAtUtc || Number.isNaN(parsedExpiresAt.getTime())) {
      setCreateError("Expires at (UTC) is required.");
      return;
    }
    if (!priceAmount.trim()) {
      setCreateError("Price amount is required.");
      return;
    }

    setCreatePending(true);
    try {
      const createdPackage = await createAdminPackage({
        student_id: studentId.trim(),
        lessons_total: parsedLessonsTotal,
        expires_at_utc: parsedExpiresAt.toISOString(),
        price_amount: priceAmount.trim(),
        price_currency: (priceCurrency.trim() || "USD").toUpperCase()
      });
      setCreateSuccess(`Package created: ${createdPackage.package_id}`);
      await loadPackages();
    } catch (requestError) {
      setCreateError(requestError instanceof Error ? requestError.message : "Failed to create package");
    } finally {
      setCreatePending(false);
    }
  }

  if (unavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Packages</p>
        <h1>Endpoint unavailable</h1>
        <p className="summary">
          Package management requires <code>GET /admin/packages</code> and
          <code>POST /admin/packages</code>.
        </p>
      </article>
    );
  }

  return (
    <article className="card section-page">
      <p className="eyebrow">Packages</p>
      <h1>Packages</h1>

      <form className="users-provision-form" onSubmit={handleCreatePackage}>
        <h2>Create package</h2>
        <label>
          <span>Student ID</span>
          <input
            type="text"
            value={studentId}
            onChange={(event) => setStudentId(event.target.value)}
            placeholder="UUID student_id"
          />
        </label>
        <label>
          <span>Lessons total</span>
          <input
            type="number"
            min={1}
            value={lessonsTotal}
            onChange={(event) => setLessonsTotal(event.target.value)}
          />
        </label>
        <label>
          <span>Expires at UTC</span>
          <input
            type="datetime-local"
            value={expiresAtUtc}
            onChange={(event) => setExpiresAtUtc(event.target.value)}
          />
        </label>
        <label>
          <span>Price amount</span>
          <input
            type="text"
            value={priceAmount}
            onChange={(event) => setPriceAmount(event.target.value)}
            placeholder="149.00"
          />
        </label>
        <label>
          <span>Currency</span>
          <input
            type="text"
            value={priceCurrency}
            onChange={(event) => setPriceCurrency(event.target.value)}
            placeholder="USD"
            maxLength={3}
          />
        </label>
        <button type="submit" disabled={createPending}>
          {createPending ? "Creating..." : "Create package"}
        </button>
        {createError ? <p className="error-text">{createError}</p> : null}
        {createSuccess ? <p className="success-text">{createSuccess}</p> : null}
      </form>

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
