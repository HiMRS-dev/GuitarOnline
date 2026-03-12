import { FormEvent, useCallback, useEffect, useState } from "react";

import { ApiClientError } from "../../shared/api/client";
import { createAdminPackage, listAdminPackages } from "../../features/packages/api";
import type { AdminPackage } from "../../features/packages/types";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);

const PACKAGE_STATUSES = ["", "active", "expired", "depleted", "canceled"];
const PACKAGE_STATUS_LABELS: Record<string, string> = {
  active: "активен",
  expired: "истёк",
  depleted: "исчерпан",
  canceled: "отменён"
};

function formatPackageStatus(status: string): string {
  return PACKAGE_STATUS_LABELS[status] ?? status;
}

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
      setError(requestError instanceof Error ? requestError.message : "Не удалось загрузить пакеты");
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
      setCreateError("ID студента обязателен.");
      return;
    }
    if (!Number.isInteger(parsedLessonsTotal) || parsedLessonsTotal <= 0) {
      setCreateError("Количество уроков должно быть положительным целым числом.");
      return;
    }
    if (!expiresAtUtc || Number.isNaN(parsedExpiresAt.getTime())) {
      setCreateError("Дата истечения (UTC) обязательна.");
      return;
    }
    if (!priceAmount.trim()) {
      setCreateError("Стоимость обязательна.");
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
      setCreateSuccess(`Пакет создан: ${createdPackage.package_id}`);
      await loadPackages();
    } catch (requestError) {
      setCreateError(
        requestError instanceof Error ? requestError.message : "Не удалось создать пакет"
      );
    } finally {
      setCreatePending(false);
    }
  }

  if (unavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Пакеты</p>
        <h1>Эндпоинт недоступен</h1>
        <p className="summary">
          Для управления пакетами требуются <code>GET /admin/packages</code> и
          <code>POST /admin/packages</code>.
        </p>
      </article>
    );
  }

  return (
    <article className="card section-page">
      <p className="eyebrow">Пакеты</p>
      <h1>Пакеты</h1>

      <form className="users-provision-form" onSubmit={handleCreatePackage}>
        <h2>Создать пакет</h2>
        <label>
          <span>ID студента</span>
          <input
            type="text"
            value={studentId}
            onChange={(event) => setStudentId(event.target.value)}
            placeholder="UUID student_id"
          />
        </label>
        <label>
          <span>Количество уроков</span>
          <input
            type="number"
            min={1}
            value={lessonsTotal}
            onChange={(event) => setLessonsTotal(event.target.value)}
          />
        </label>
        <label>
          <span>Истекает в (UTC)</span>
          <input
            type="datetime-local"
            value={expiresAtUtc}
            onChange={(event) => setExpiresAtUtc(event.target.value)}
          />
        </label>
        <label>
          <span>Стоимость</span>
          <input
            type="text"
            value={priceAmount}
            onChange={(event) => setPriceAmount(event.target.value)}
            placeholder="149.00"
          />
        </label>
        <label>
          <span>Валюта</span>
          <input
            type="text"
            value={priceCurrency}
            onChange={(event) => setPriceCurrency(event.target.value)}
            placeholder="USD"
            maxLength={3}
          />
        </label>
        <button type="submit" disabled={createPending}>
          {createPending ? "Создание..." : "Создать пакет"}
        </button>
        {createError ? <p className="error-text">{createError}</p> : null}
        {createSuccess ? <p className="success-text">{createSuccess}</p> : null}
      </form>

      <label className="inline-filter">
        <span>Статус</span>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          {PACKAGE_STATUSES.map((status) => (
            <option key={status || "all"} value={status}>
              {status ? formatPackageStatus(status) : "все"}
            </option>
          ))}
        </select>
      </label>

      {loading ? <p className="summary">Загрузка пакетов...</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      {!loading && !error ? (
        packages.length ? (
          <div className="bookings-table-wrap">
            <table className="bookings-table">
              <thead>
                <tr>
                  <th>Пакет</th>
                  <th>Студент</th>
                  <th>Статус</th>
                  <th>Осталось</th>
                  <th>Зарезервировано</th>
                  <th>Цена</th>
                  <th>Истекает</th>
                </tr>
              </thead>
              <tbody>
                {packages.map((pkg) => (
                  <tr key={pkg.package_id}>
                    <td>{pkg.package_id.slice(0, 8)}</td>
                    <td>{pkg.student_id.slice(0, 8)}</td>
                    <td>{formatPackageStatus(pkg.status)}</td>
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
          <p className="summary">По выбранному фильтру пакеты не найдены.</p>
        )
      ) : null}
    </article>
  );
}
