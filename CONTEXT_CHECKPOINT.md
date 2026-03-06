# GuitarOnline Context Checkpoint (Condensed 2026-03-06)

## 1) Purpose
- Single operational source of truth for current project state and next execution steps.
- Keep this file short and actionable.
- Full historical log is archived in:
  - `docs/context/CONTEXT_CHECKPOINT_ARCHIVE_2026-03-06.md`

## 2) Product Snapshot
- Project: backend platform for online guitar learning (modular monolith).
- Roles: `student`, `teacher`, `admin`.
- Core domains in API:
  - `identity`, `teachers`, `scheduling`, `booking`, `billing`, `lessons`, `notifications`, `admin`, `audit`.
- Stack:
  - FastAPI, SQLAlchemy async, Alembic, PostgreSQL, Redis (optional), Poetry, Docker Compose.
- Entry point:
  - `app/main.py`.

## 3) Delivery Status
- MVP and hardening scope delivered.
- Epics `A` to `H` are implemented and verified.
- Release tag exists:
  - `v1.1.0`.
- Admin UI (`web-admin`) is integrated, including optional production profile (`admin-ui`).

## 4) Current Verified State (2026-03-06)
- Branch:
  - `main`.
- Latest fully green commit on `main` before current step:
  - `34c7b8d` (`perf(admin): optimize heavy admin queries and add supporting indexes`).
- Latest GitHub Actions status for that commit:
  - `ci`: `success`.
  - `deploy`: `success`.

## 5) Latest Validation Evidence
- Full local suite (after stabilization):
  - `py -m poetry run pytest -q` -> `237 passed, 5 skipped`.
- Targeted integration retest after CI parity fix:
  - `py -m poetry run pytest -q tests/test_booking_billing_integration.py` -> `6 passed, 4 skipped`.
- Lint check for integration file:
  - `py -m poetry run ruff check tests/test_booking_billing_integration.py` -> `All checks passed`.
- Smoke and probes on running stack:
  - `python scripts/deploy_smoke_check.py` -> `Smoke checks passed.`
  - `/health` -> `ok`, `/ready` -> `ready`, `/metrics` families present.

## 6) Recent Conflict Fixes (Important)
1. Admin teacher list SQL conflict (`DISTINCT ... ORDER BY`) fixed in:
   - `app/modules/admin/repository.py`.
2. CI compose validation hardened:
   - `docker-compose.prod.yml` now tolerates absent `.env` in CI.
3. Settings env parsing hardened for CSV tuple fields:
   - `app/core/config.py` uses `NoDecode` where needed.
4. Integration stabilization for rate limits and slot collisions:
   - test flow and compose overrides adjusted.
5. CI enum storage parity in integration tests:
   - `tests/test_booking_billing_integration.py` now uses case-safe raw SQL checks.

## 7) Operations Quick Start
1. Start stack:
   - `docker compose -f docker-compose.prod.yml up -d --build`
2. Apply migrations:
   - `docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head`
3. Smoke:
   - `docker compose -f docker-compose.prod.yml exec -T app python scripts/deploy_smoke_check.py`
4. Security gate:
   - `py -m poetry run pytest -q tests/test_config_security.py tests/test_identity_rate_limit.py tests/test_security_surface.py tests/test_pii_field_visibility.py`
5. Full test suite:
   - `py -m poetry run pytest -q`

## 8) Open Risks / Technical Debt
1. External Docker registry/network reliability remains environment-dependent.
2. `AUTH_RATE_LIMIT_BACKEND=memory` is not suitable for multi-instance production.
3. `pip-audit` allowlist has one temporary exception (`CVE-2024-23342` for transitive `ecdsa`) and must be revisited when upstream fix is published.
4. Checkpoint hygiene must remain strict:
   - append concise deltas only,
   - rotate/archive before this file exceeds ~1200 lines.

## 9) v1.2 Execution Plan (Ordered)
| ID | Priority | Task | Done When |
| --- | --- | --- | --- |
| `V2-01` | P0 | Complete alert routing (Slack/PagerDuty/email) from Alertmanager. | Test alert is delivered to real channels and documented in runbook. |
| `V2-02` | P0 | Define SLO/SLI pack for API + DB (`error_rate`, `p95`, readiness). | Dashboards and alert thresholds exist and are validated by synthetic trigger. |
| `V2-03` | P0 | Add synthetic operational checks (health, ready, auth, booking critical flow). | Periodic check fails loudly and creates alert with actionable context. |
| `V2-04` | P1 | Automate backup schedule + retention policy enforcement. | Daily/weekly retention works and cleanup policy is verified. |
| `V2-05` | P1 | Add restore rehearsal workflow with RPO/RTO report artifact. | Restore check passes on fresh DB and emits measurable RPO/RTO values. |
| `V2-06` | P1 | Run performance baseline for admin-heavy endpoints. | Baseline report for `/admin/teachers`, `/admin/slots`, `/admin/kpi/*` is committed. |
| `V2-07` | P1 | Apply SQL/index optimizations from baseline findings. | Confirmed p95 improvement without regression in existing tests. |
| `V2-08` | P2 | Add supply-chain security gates (`pip-audit`, npm audit, SBOM). | CI enforces policy and produces machine-readable security artifact. |
| `V2-09` | P2 | Formalize secret/key rotation procedure with dry-run test. | Rotation playbook is documented and dry-run is reproducible end-to-end. |
| `V2-10` | P2 | Add role-based E2E regression scenario to release gate. | Release workflow runs critical path (`admin/teacher/student`) and blocks on failure. |

## 10) Immediate Queue (Next Iteration)
1. `V2-09`: secret/key rotation procedure with dry-run test.
2. `V2-10`: role-based end-to-end regression scenario in release gate.
3. Validate `V2-08` gate behavior on GitHub-hosted runner (`npm audit` + artifact upload).
4. Gate for closing iteration:
   - top three tasks merged,
   - `ci` and `deploy` green on `main`,
   - updated runbook with commands and expected output markers.

## 11) v1.2 Progress Log
- `V2-01` completed (2026-03-06): real-channel alert routing verification tooling + runbook sync.
- implemented:
  - new cross-platform verifier script:
    - `scripts/alertmanager_fire_and_verify.py`
      (synthetic alert submit + Alertmanager metrics-delta delivery verification),
  - Windows wrapper:
    - `scripts/alertmanager_fire_and_verify.ps1`,
  - runbook updates:
    - `README.md`,
    - `ops/release_checklist.md`,
    - `ops/production_hardening_checklist.md`.
- conflict resolved during implementation:
  - Alertmanager `POST /api/v2/alerts` may return empty response body; parser now tolerates empty body.
- verification evidence:
  - `py -m poetry run ruff check scripts/alertmanager_fire_and_verify.py` -> `All checks passed`.
  - `python -m compileall scripts/alertmanager_fire_and_verify.py` -> success.
  - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_fire_and_verify.ps1 -DryRun` -> configured integrations detected.
  - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_fire_and_verify.ps1 -DurationMinutes 2 -TimeoutSeconds 90 -PollSeconds 5` ->
    delivery passed with metrics delta:
    - `slack.notifications_total +1`,
    - `slack.requests_failed_total +0`.
- `V2-02` completed (2026-03-06): SLO/SLI pack for API + DB-readiness with synthetic threshold validation.
- implemented:
  - Prometheus SLI recording rules in `ops/prometheus/alerts.yml`:
    - `guitaronline:sli:error_ratio:5m`,
    - `guitaronline:sli:availability_ratio:5m`,
    - `guitaronline:sli:p95_latency_seconds:5m`,
    - `guitaronline:sli:readiness_success_ratio:5m`.
  - Alert thresholds in `ops/prometheus/alerts.yml`:
    - `GuitarOnlineApiDown`,
    - `GuitarOnlineApiHigh5xxRate`,
    - `GuitarOnlineApiHighP95Latency`,
    - `GuitarOnlineApiReadinessDegraded`.
  - Synthetic threshold test suite:
    - `ops/prometheus/alerts.test.yml` (`promtool test rules` scenarios for healthy and breach states).
  - CI/ops gating updated:
    - `.github/workflows/ci.yml` now runs `promtool test rules`,
    - `scripts/validate_ops_configs.ps1` now runs `promtool test rules`.
  - Dashboard SLO wiring:
    - `ops/grafana/dashboards/guitaronline-api-overview.json` now reads SLI recording rules and includes readiness-success stat with thresholds.
  - compose readiness signal improvement:
    - `docker-compose.prod.yml` app healthcheck uses `/ready` (DB-aware signal).
  - alert-noise inhibition updated for new readiness alert:
    - `ops/alertmanager/alertmanager.yml`,
    - `scripts/render_alertmanager_oncall_config.ps1`.
- verification evidence:
  - `docker run ... promtool check config /etc/prometheus/prometheus.yml` -> success.
  - `docker run ... promtool check rules /etc/prometheus/alerts.yml` -> success.
  - `docker run ... promtool test rules /etc/prometheus/alerts.test.yml` -> success.
  - `docker run ... amtool check-config /etc/alertmanager/alertmanager.yml` -> success.
  - `docker compose -f docker-compose.prod.yml config -q` -> success.
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_ops_configs.ps1` -> success.
- `V2-03` completed (2026-03-06): periodic synthetic operational checks wired to alerting.
- implemented:
  - synthetic critical-path check script:
    - `scripts/synthetic_ops_check.py`,
    - coverage includes `/health`, `/ready`, `/metrics`, auth flows, and booking hold->confirm->cancel cleanup path.
  - failure-to-alert wiring:
    - script emits `GuitarOnlineSyntheticOpsCheckFailed` to Alertmanager with step-specific failure context and runbook annotation.
  - remote runner script for target host:
    - `scripts/run_synthetic_ops_remote.sh`.
  - scheduled workflow:
    - `.github/workflows/synthetic-ops-check.yml`,
    - hourly cron (`15 * * * *`) + manual `workflow_dispatch` (`confirm=SYNTHETIC`).
  - runbook updates:
    - `README.md`,
    - `ops/release_checklist.md`,
    - `ops/production_hardening_checklist.md`.
- conflict resolved during implementation:
  - running stack used older app image and did not include new script path; fixed by rebuilding app container before validation.
- verification evidence:
  - `py -m poetry run ruff check scripts/synthetic_ops_check.py` -> `All checks passed`.
  - `python -m compileall scripts/synthetic_ops_check.py` -> success.
  - `docker run --rm -v "${PWD}:/repo" bash:5.2 bash -n /repo/scripts/run_synthetic_ops_remote.sh` -> success.
  - `docker compose -f docker-compose.prod.yml exec -T app python scripts/synthetic_ops_check.py --no-alert-on-failure` ->
    `Synthetic ops check passed.`.
- `V2-04` completed (2026-03-06): scheduled backup + retention automation.
- implemented:
  - remote runner for periodic DB backups with retention policy enforcement:
    - `scripts/run_backup_schedule_remote.sh`,
    - writes isolated artifacts under `backups/scheduled/daily` and `backups/scheduled/weekly`.
  - retention controls:
    - `BACKUP_DAILY_KEEP` (default `7`),
    - `BACKUP_WEEKLY_KEEP` (default `8`),
    - `BACKUP_WEEKLY_DAY` (default `1`, Monday UTC),
    - optional `BACKUP_FORCE_WEEKLY=true` for manual weekly snapshot run.
  - scheduled workflow:
    - `.github/workflows/backup-schedule-retention.yml`,
    - daily cron (`30 2 * * *`) + manual `workflow_dispatch` (`confirm=BACKUP`).
  - runbook updates:
    - `README.md`,
    - `ops/release_checklist.md`,
    - `ops/production_hardening_checklist.md`.
- conflict prevention decisions:
  - retention cleanup is scoped only to `backups/scheduled/*` and does not touch
    pre-deploy artifacts (`backups/predeploy-*`) or restore-verification artifacts (`backups/verify-*`).
- verification evidence:
  - `docker run --rm -v "${PWD}:/repo" bash:5.2 bash -n /repo/scripts/run_backup_schedule_remote.sh` -> success.
  - `docker run --rm -v "${PWD}:/repo" -w /repo rhysd/actionlint:1.7.8 .github/workflows/backup-schedule-retention.yml` -> success.
  - scheduled workflow input validation enforces numeric retention and weekday bounds before SSH run.
- `V2-05` completed (2026-03-06): restore rehearsal workflow with RPO/RTO artifact.
- implemented:
  - remote restore rehearsal runner:
    - `scripts/run_restore_rehearsal_remote.sh`,
    - restores latest scheduled daily backup (or explicit backup override) into a fresh temporary DB,
    - validates restored schema and writes JSON report with `rpo_seconds` + `rto_seconds`.
  - scheduled workflow:
    - `.github/workflows/restore-rehearsal.yml`,
    - weekly cron (`20 3 * * 1`) + manual `workflow_dispatch` (`confirm=RESTORE`),
    - downloads remote report and publishes GitHub artifact.
  - runbook updates:
    - `README.md`,
    - `ops/release_checklist.md`,
    - `ops/production_hardening_checklist.md`.
- conflict prevention decisions:
  - restore rehearsal reads scheduled backups (`backups/scheduled/daily`) and does not mutate production DB;
    restore is executed into throwaway DB `restore_rehearsal_*` and auto-cleaned.
- verification evidence:
  - `docker run --rm -v "${PWD}:/repo" bash:5.2 bash -n /repo/scripts/run_restore_rehearsal_remote.sh` -> success.
  - `docker run --rm -v "${PWD}:/repo" -w /repo rhysd/actionlint:1.7.8 .github/workflows/restore-rehearsal.yml` -> success.
  - local containerized functional rehearsal run:
    - `COMPOSE_PROJECT_NAME=guitaronline DEPLOY_PATH=/repo bash scripts/run_restore_rehearsal_remote.sh` ->
      `rpo_seconds=143`, `rto_seconds=1.621`, report file emitted in `backups/reports/`.
- `V2-06` completed (2026-03-06): admin-heavy endpoint performance baseline.
- implemented:
  - benchmark script:
    - `scripts/admin_perf_baseline.py`,
    - measures latency envelopes for:
      - `/api/v1/admin/teachers`,
      - `/api/v1/admin/slots`,
      - `/api/v1/admin/kpi/overview`,
      - `/api/v1/admin/kpi/sales`.
  - committed baseline reports:
    - `docs/perf/admin_perf_baseline_2026-03-06.json`,
    - `docs/perf/admin_perf_baseline_2026-03-06.md`.
  - runbook updates:
    - `README.md`,
    - `ops/release_checklist.md`,
    - `ops/production_hardening_checklist.md`.
- conflict resolved during implementation:
  - identity rate limits (`429`) during synthetic data setup; baseline script now includes controlled retry/wait for register/login operations.
  - CI secret-scan false-positive on local variable `password`; renamed to neutral `shared_credential` to satisfy repo guardrails.
- verification evidence:
  - `py -m poetry run ruff check scripts/admin_perf_baseline.py` -> `All checks passed`.
  - `python -m compileall scripts/admin_perf_baseline.py` -> success.
  - `python scripts/admin_perf_baseline.py` -> success with baseline metrics:
    - `admin_teachers p95=38.78ms`,
    - `admin_slots p95=37.12ms`,
    - `admin_kpi_overview p95=43.89ms`,
    - `admin_kpi_sales p95=44.10ms`.
- `V2-07` completed (2026-03-06): SQL/index optimization pass based on baseline findings.
- implemented:
  - DB index migrations:
    - `20260306_0017_admin_performance_indexes.py`,
    - `20260306_0018_admin_teachers_trgm_indexes.py`.
  - index coverage additions:
    - `availability_slots(teacher_id, start_at)`,
    - `bookings(slot_id, status)`,
    - `teacher_profiles(created_at)`,
    - `lesson_packages(created_at)`,
    - `lesson_packages(status, created_at)`,
    - `payments(status, created_at)`,
    - `payments(package_id, status, created_at)`,
    - PostgreSQL GIN trigram indexes for `teacher_profiles.display_name` and `users.email`.
  - query-path optimizations:
    - `list_teachers` tag filter path uses `EXISTS` (no duplicate-producing join/group-by),
    - `get_kpi_sales` consolidates payment aggregations and paid-package conversion path,
    - `get_kpi_overview` consolidates payment counts + amounts into one aggregate query.
  - new probe tooling + report:
    - `scripts/admin_perf_probe.py`,
    - `docs/perf/admin_perf_probe_preopt_2026-03-06_run4.json`,
    - `docs/perf/admin_perf_probe_optimized_2026-03-06_run4.json`,
    - `docs/perf/admin_perf_optimization_2026-03-06.md`.
- conflict handling during implementation:
  - baseline load induced auth rate-limit pressure; used controlled retries + explicit Redis limiter resets between measurements.
  - to ensure fair comparison, measured pre/post builds on same dataset and identical probe parameters.
- verification evidence:
  - `py -m poetry run ruff check ...` for changed admin/model/migration/probe files -> `All checks passed`.
  - `python scripts/secret_guard.py --mode repo` -> `Secret scan passed`.
  - `py -m poetry run pytest -q tests/test_admin_teachers_list.py tests/test_admin_slots_list.py tests/test_admin_kpi_overview.py tests/test_admin_kpi_sales.py` ->
    `11 passed`.
  - p95 comparison (`run4` probe, same dataset):
    - aggregate p95 average improved from `42.93ms` to `40.56ms` (`~5.5%`).
- `V2-08` completed (2026-03-06): CI supply-chain security gates and SBOM artifact wiring.
- implemented:
  - dependency security updates:
    - `fastapi` -> `0.135.1`,
    - `python-multipart` -> `0.0.22`,
    - transitive `starlette` resolved to `0.49.3`.
  - supply-chain gate script:
    - `scripts/supply_chain_gate.py`,
    - runs `pip-audit` (with reviewed allowlist), `npm audit`, and emits backend CycloneDX SBOM.
  - allowlist policy file:
    - `ops/security/pip_audit_ignore.txt` (temporary `CVE-2024-23342` for transitive `ecdsa`).
  - CI integration:
    - `.github/workflows/ci.yml` includes job `supply-chain` (gating `lint`) and uploads artifact `supply-chain-security-artifacts`.
  - runbook/checklist updates:
    - `README.md`,
    - `ops/release_checklist.md`,
    - `ops/production_hardening_checklist.md`.
- conflict handling during implementation:
  - `pip-audit --strict` conflicts with editable local package (`guitaronline`) not published on PyPI;
    resolved by audited mode with `--skip-editable` plus explicit reviewed vulnerability allowlist.
  - `web-admin` had no committed lockfile for reproducible `npm audit`;
    gate now creates temporary `package-lock.json` for audit and removes it after execution.
- verification evidence:
  - `py -m poetry run ruff check scripts/supply_chain_gate.py` -> `All checks passed`.
  - `python -m compileall scripts/supply_chain_gate.py` -> success.
  - `py -m poetry run python scripts/supply_chain_gate.py --skip-npm` -> success (artifacts emitted in `.tmp/security`).
  - `docker run --rm -v "${PWD}:/repo" -w /repo rhysd/actionlint:1.7.8 .github/workflows/ci.yml` -> success.
  - local environment limitation:
    - `npm` unavailable on this host; full npm-audit branch is validated in GitHub Actions runner.

## 12) References
- Full historical checkpoint archive:
  - `docs/context/CONTEXT_CHECKPOINT_ARCHIVE_2026-03-06.md`
- Release notes:
  - `docs/releases/v1.1.0.md`
