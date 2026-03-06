# Admin Endpoint Performance Baseline

- Generated at (UTC): `2026-03-06T11:34:09+00:00`
- Base URL: `http://localhost:8000`
- Warmup requests per endpoint: `5`
- Measured requests per endpoint: `30`
- Synthetic teacher profiles created: `10`
- Synthetic slots created: `600`

## Results

| Endpoint | Avg (ms) | P50 (ms) | P95 (ms) | Max (ms) | Samples |
| --- | ---: | ---: | ---: | ---: | ---: |
| `admin_teachers` | 28.26 | 22.83 | 45.87 | 52.11 | 30 |
| `admin_slots` | 26.58 | 25.91 | 38.48 | 44.35 | 30 |
| `admin_kpi_overview` | 29.06 | 23.26 | 43.85 | 99.55 | 30 |
| `admin_kpi_sales` | 22.42 | 20.38 | 38.32 | 40.72 | 30 |

## Endpoints

- `admin_teachers`: `/api/v1/admin/teachers?q=perf-baseline-095b8161ea&limit=100&offset=0`
- `admin_slots`: `/api/v1/admin/slots?teacher_id=63d0c727-e346-4449-bac2-10e0b54976d2&from_utc=2026-03-09T00%3A00%3A00%2B00%3A00&to_utc=2026-06-21T23%3A59%3A59%2B00%3A00&limit=100&offset=0`
- `admin_kpi_overview`: `/api/v1/admin/kpi/overview`
- `admin_kpi_sales`: `/api/v1/admin/kpi/sales?from_utc=2025-09-07T11%3A34%3A05%2B00%3A00&to_utc=2026-03-06T11%3A34%3A05%2B00%3A00`
