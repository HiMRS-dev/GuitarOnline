# Admin Performance Optimization Report (2026-03-06)

## Scope

- Goal: apply SQL/query optimizations after baseline and confirm p95 improvement.
- Compared builds on the same dataset and benchmark inputs:
  - pre-optimization app: `http://localhost:8001` (`78fd529` image),
  - optimized app: `http://localhost:8000` (current code with `V2-07` changes).
- Probe config:
  - warmup: `5`,
  - measured requests: `30`,
  - teacher token: `perf-baseline-28aa1ce8b4`,
  - teacher id: `ed0f1321-bd3c-402a-bf2a-f8e5602bc6dc`,
  - slot window: `2026-03-09T00:00:00+00:00` .. `2026-06-21T23:59:59+00:00`.

## p95 Comparison

| Endpoint | Pre p95 (ms) | Optimized p95 (ms) | Delta (ms) |
| --- | ---: | ---: | ---: |
| `admin_teachers` | 42.43 | 42.58 | +0.15 |
| `admin_slots` | 40.93 | 40.29 | -0.64 |
| `admin_kpi_overview` | 46.81 | 43.38 | -3.43 |
| `admin_kpi_sales` | 41.55 | 35.98 | -5.57 |

Aggregate p95 average:

- pre: `42.93 ms`
- optimized: `40.56 ms`
- delta: `-2.37 ms` (`~5.5%` improvement)

## Implemented Changes

- Added composite and selective indexes for admin-heavy reads:
  - `availability_slots(teacher_id, start_at)`,
  - `bookings(slot_id, status)`,
  - `teacher_profiles(created_at)`,
  - `lesson_packages(created_at)`,
  - `lesson_packages(status, created_at)`,
  - `payments(status, created_at)`,
  - `payments(package_id, status, created_at)`.
- Added PostgreSQL trigram support for admin search:
  - `teacher_profiles.display_name` GIN trgm index,
  - `users.email` GIN trgm index.
- Optimized repository query paths:
  - `list_teachers`: removed unnecessary `GROUP BY` via tag `EXISTS` filter path.
  - `get_kpi_sales`: consolidated payment aggregates and reduced scan complexity for paid-package conversion.
  - `get_kpi_overview`: consolidated payment counts/sums into a single aggregate query.

## Evidence Artifacts

- pre probe: `docs/perf/admin_perf_probe_preopt_2026-03-06_run4.json`
- optimized probe: `docs/perf/admin_perf_probe_optimized_2026-03-06_run4.json`
