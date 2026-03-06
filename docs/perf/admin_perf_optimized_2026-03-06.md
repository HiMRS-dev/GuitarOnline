# Admin Endpoint Performance Baseline

- Generated at (UTC): `2026-03-06T09:19:43+00:00`
- Base URL: `http://localhost:8000`
- Warmup requests per endpoint: `5`
- Measured requests per endpoint: `30`
- Synthetic teacher profiles created: `10`
- Synthetic slots created: `600`

## Results

| Endpoint | Avg (ms) | P50 (ms) | P95 (ms) | Max (ms) | Samples |
| --- | ---: | ---: | ---: | ---: | ---: |
| `admin_teachers` | 32.29 | 32.55 | 42.10 | 42.96 | 30 |
| `admin_slots` | 31.68 | 32.10 | 39.28 | 42.80 | 30 |
| `admin_kpi_overview` | 32.27 | 33.51 | 46.11 | 51.40 | 30 |
| `admin_kpi_sales` | 29.45 | 31.24 | 39.34 | 40.16 | 30 |

## Endpoints

- `admin_teachers`: `/api/v1/admin/teachers?q=perf-baseline-ba5c8da5c4&limit=100&offset=0`
- `admin_slots`: `/api/v1/admin/slots?teacher_id=76852e1d-f239-48b0-9146-1a78d83a3176&from_utc=2026-03-09T00%3A00%3A00%2B00%3A00&to_utc=2026-06-21T23%3A59%3A59%2B00%3A00&limit=100&offset=0`
- `admin_kpi_overview`: `/api/v1/admin/kpi/overview`
- `admin_kpi_sales`: `/api/v1/admin/kpi/sales?from_utc=2025-09-07T09%3A19%3A38%2B00%3A00&to_utc=2026-03-06T09%3A19%3A38%2B00%3A00`
