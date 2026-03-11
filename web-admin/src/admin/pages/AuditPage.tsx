import { useEffect, useState } from "react";

import { ApiClientError, apiClient } from "../../shared/api/client";
import type { PageResponse } from "../../shared/api/types";

const UNAVAILABLE_STATUSES = new Set([404, 405, 501]);
const PAGE_LIMIT = 50;

type AdminAction = {
  id: string;
  admin_id: string;
  action: string;
  target_type: string;
  target_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export function AuditPage() {
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState<AdminAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setUnavailable(false);
    apiClient
      .request<PageResponse<AdminAction>>(`/admin/actions?limit=${PAGE_LIMIT}&offset=${offset}`)
      .then((page) => {
        setItems(page.items);
        setTotal(page.total);
      })
      .catch((requestError) => {
        if (
          requestError instanceof ApiClientError &&
          UNAVAILABLE_STATUSES.has(requestError.status)
        ) {
          setUnavailable(true);
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "Failed to load audit log");
      })
      .finally(() => setLoading(false));
  }, [offset]);

  if (unavailable) {
    return (
      <article className="card section-page">
        <p className="eyebrow">Audit</p>
        <h1>Endpoint unavailable</h1>
        <p className="summary">
          Audit page requires <code>GET /admin/actions</code>.
        </p>
      </article>
    );
  }

  return (
    <article className="card section-page">
      <p className="eyebrow">Audit</p>
      <h1>Admin Actions Journal</h1>

      <div className="calendar-actions">
        <button
          type="button"
          onClick={() => setOffset((current) => Math.max(current - PAGE_LIMIT, 0))}
          disabled={offset === 0 || loading}
        >
          Prev
        </button>
        <button
          type="button"
          onClick={() =>
            setOffset((current) => (current + PAGE_LIMIT < total ? current + PAGE_LIMIT : current))
          }
          disabled={loading || offset + PAGE_LIMIT >= total}
        >
          Next
        </button>
      </div>

      <p className="summary">
        Showing {items.length ? offset + 1 : 0}-{offset + items.length} of {total}
      </p>
      {loading ? <p className="summary">Loading actions...</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      {!loading && !error ? (
        items.length ? (
          <div className="bookings-table-wrap">
            <table className="bookings-table">
              <thead>
                <tr>
                  <th>Time (UTC)</th>
                  <th>Action</th>
                  <th>Target</th>
                  <th>Payload</th>
                  <th>Admin</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{new Date(item.created_at).toISOString()}</td>
                    <td>{item.action}</td>
                    <td>
                      {item.target_type}
                      {item.target_id ? `:${item.target_id}` : ""}
                    </td>
                    <td>
                      <code>{JSON.stringify(item.payload)}</code>
                    </td>
                    <td>{item.admin_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="summary">No audit actions found.</p>
        )
      ) : null}
    </article>
  );
}
