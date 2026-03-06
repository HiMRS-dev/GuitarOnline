# Admin Endpoint Performance Baseline

- Generated at (UTC): `2026-03-06T08:54:37+00:00`
- Base URL: `http://localhost:8000`
- Warmup requests per endpoint: `5`
- Measured requests per endpoint: `30`
- Synthetic teacher profiles created: `10`
- Synthetic slots created: `600`

## Results

| Endpoint | Avg (ms) | P50 (ms) | P95 (ms) | Max (ms) | Samples |
| --- | ---: | ---: | ---: | ---: | ---: |
| `admin_teachers` | 28.24 | 29.05 | 38.78 | 39.81 | 30 |
| `admin_slots` | 25.40 | 23.51 | 37.12 | 37.51 | 30 |
| `admin_kpi_overview` | 30.24 | 31.14 | 43.89 | 46.55 | 30 |
| `admin_kpi_sales` | 29.37 | 27.51 | 44.10 | 46.66 | 30 |

## Endpoints

- `admin_teachers`: `/api/v1/admin/teachers?q=perf-baseline-28aa1ce8b4&limit=100&offset=0`
- `admin_slots`: `/api/v1/admin/slots?teacher_id=ed0f1321-bd3c-402a-bf2a-f8e5602bc6dc&from_utc=2026-03-09T00%3A00%3A00%2B00%3A00&to_utc=2026-06-21T23%3A59%3A59%2B00%3A00&limit=100&offset=0`
- `admin_kpi_overview`: `/api/v1/admin/kpi/overview`
- `admin_kpi_sales`: `/api/v1/admin/kpi/sales?from_utc=2025-09-07T08%3A54%3A33%2B00%3A00&to_utc=2026-03-06T08%3A54%3A33%2B00%3A00`
