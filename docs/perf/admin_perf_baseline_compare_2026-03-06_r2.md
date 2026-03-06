# Admin Performance Baseline Comparison (2026-03-06 R2)

## Inputs

- Baseline A:
  - `docs/perf/admin_perf_baseline_2026-03-06.json`
- Baseline B:
  - `docs/perf/admin_perf_baseline_2026-03-06_r2.json`

## P95 Delta

| Endpoint | P95 A (ms) | P95 B (ms) | Delta (ms) | Delta (%) |
| --- | ---: | ---: | ---: | ---: |
| `admin_teachers` | 38.78 | 45.87 | +7.09 | +18.28% |
| `admin_slots` | 37.12 | 38.48 | +1.36 | +3.66% |
| `admin_kpi_overview` | 43.89 | 43.85 | -0.04 | -0.09% |
| `admin_kpi_sales` | 44.10 | 38.32 | -5.78 | -13.11% |

- Average P95 across endpoints:
  - Baseline A: `40.97 ms`
  - Baseline B: `41.63 ms`
  - Delta: `+0.66 ms` (`+1.60%`)

## Conclusion

- `admin_kpi_sales` improved materially.
- `admin_teachers` regressed and dominates aggregate delta.
- Overall profile is mixed; no uniform p95 improvement in this run.

## Follow-Up Actions

1. Re-run benchmark in isolated window after limiter cooldown to reduce registration setup noise.
2. Run focused probe for `admin_teachers` (`q` search path) with stable synthetic dataset size.
3. If regression repeats, inspect query plan and cache/IO behavior for teacher search path.
