# GuitarOnline Context Checkpoint (Updated 2026-02-26)

## 1) Product Context
- Project: backend for an online guitar learning platform (modular monolith).
- Core roles: `student`, `teacher`, `admin`.
- Core domains: identity/auth, teacher profiles, scheduling, booking, billing, lessons, notifications, audit/outbox.
- Main business rules already implemented in booking:
  - hold expiration (`BOOKING_HOLD_MINUTES`, default 10 min),
  - cancellation refund window (`BOOKING_REFUND_WINDOW_HOURS`, default 24 h),
  - reschedule = cancel + new booking.

## 2) Current Repository Snapshot
- Framework stack: FastAPI + SQLAlchemy async + Alembic + PostgreSQL + Poetry.
- Entrypoint: `app/main.py`.
- API modules currently wired in app:
  - `identity`, `teachers`, `scheduling`, `booking`, `billing`, `lessons`, `notifications`, `admin`, `audit`.
- Migration state:
  - `alembic/versions/20260219_0001_initial_schema.py` exists and is applied.
- Tests currently in repo:
  - `tests/test_booking_rules.py` (unit tests for booking rules + idempotency).
  - `tests/test_billing_payment_rules.py` (billing reconciliation and edge-case hardening).
  - `tests/test_outbox_notifications_worker.py` (outbox worker behavior and retries).
  - `tests/test_notifications_delivery_metrics.py` (delivery observability metrics).
  - `tests/test_admin_kpi_overview.py` (admin KPI read model + traceability).
  - `tests/test_admin_operations_overview.py` (admin operational read model + traceability).
  - `tests/test_config_security.py` (environment secret-key guardrails).
  - `tests/test_rate_limiter.py` (core sliding-window limiter behavior).
  - `tests/test_identity_rate_limit.py` (identity endpoint rate-limit dependencies).
  - `tests/test_health_readiness.py` (readiness probe behavior).
  - `tests/test_metrics_observability.py` (Prometheus metrics endpoint and instrumentation).
  - `tests/test_landing_page.py` (root landing page content and links).
  - `tests/test_portal_page.py` (frontend MVP portal route serving).
  - `tests/test_booking_billing_integration.py` (HTTP+DB integration scenarios).

## 3) Baseline Implemented In This Session
- Fixed settings/env parsing crash:
  - `app/core/config.py` now uses `extra="ignore"` in `SettingsConfigDict`.
- Fixed Alembic model import:
  - `alembic/env.py` uses `import app.modules`.
- Fixed Docker image build dependency layer:
  - `Dockerfile` uses `poetry install ... --no-root` before copying app package.
- Added missing runtime dependency:
  - `email-validator` added in `pyproject.toml` / `poetry.lock`.
- Added booking rule unit tests:
  - `tests/test_booking_rules.py`.

## 4) Infrastructure Baseline (Validated)
- Docker Desktop and compose stack are operational.
- `docker compose up --build -d` succeeds.
- Runtime status:
  - `guitaronline-db` is `healthy`.
  - `guitaronline-api` is `up`.
- API availability:
  - `http://localhost:8000/docs` returns HTTP 200.
- Migrations in container:
  - `docker compose exec -T app alembic upgrade head` executed (no pending upgrades).
- Test status:
  - `py -m poetry run pytest -q` => `4 passed`.

## 5) Host-Level Network Stabilization (Outside Repo)
- Docker daemon config (`C:\Users\User\.docker\daemon.json`):
  - `dns = ["1.1.1.1", "8.8.8.8"]`
  - `mtu = 1400`
  - `max-concurrent-downloads = 1`
  - `registry-mirrors = ["https://mirror.gcr.io"]`
- WSL config (`C:\Users\User\.wslconfig`):
  - `networkingMode=nat`
  - `dnsTunneling=true`
  - `autoProxy=false`
- Docker Desktop settings store (`C:\Users\User\AppData\Roaming\Docker\settings-store.json`):
  - proxy policy switched to manual/direct.
  - backup created: `settings-store.json.bak-20260219-225319`.

## 6) Known Risks / Open Technical Debt
- Docker Hub connectivity is still flaky in this environment:
  - mitigated by `mirror.gcr.io`,
  - mitigated in-repo by `scripts/docker_warmup.ps1` (pull with retries) and
    `pull_policy: if_not_present` in `docker-compose.prod.yml`,
  - mitigated by image cache export/import scripts:
    - `scripts/docker_cache_export.ps1`,
    - `scripts/docker_cache_import.ps1`,
  - still an external dependency and cannot be fully eliminated at repo level.
- Identity rate limiting now supports shared Redis backend:
  - `AUTH_RATE_LIMIT_BACKEND=redis` uses cross-instance limiter state via Redis,
  - fallback `memory` backend remains process-local and should be used only for dev/single-instance mode,
  - for production with `memory`, explicit acknowledgement remains required:
    `AUTH_RATE_LIMIT_ALLOW_IN_MEMORY_IN_PRODUCTION=true`,
  - `X-Forwarded-For` is trusted only from configured proxies (`AUTH_RATE_LIMIT_TRUSTED_PROXY_IPS`).
- Monitoring stack remains lightweight:
  - Prometheus + Alertmanager + Grafana baseline is wired in production compose,
  - external on-call receivers (Slack/PagerDuty/email) are not configured yet,
  - onboarding template is prepared at `ops/alertmanager/alertmanager.receivers.example.yml`.

## 7) Tomorrow Quick Start (5-10 min)
1. `docker desktop status`
2. `docker compose ps`
3. `docker compose exec -T app alembic upgrade head`
4. `py -m poetry run pytest -q`
5. Open `http://localhost:8000/docs`

If any startup issue:
1. `docker info` (confirm mirror is present)
2. `docker compose logs app`
3. `docker compose logs db`

## 8) Exact Plan For Next Session (In Order)

### Step A: Baseline commit (infra + tests) (Completed 2026-02-23)
Goal: freeze stable local baseline before new functional changes.

Tasks:
1. Add `.gitignore` first (must include at least `.env`, `.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache`).
2. Verify `git status` and ensure `.env` is not tracked.
3. Commit baseline changes with a clear message, for example:
   - `chore: stabilize docker/wsl baseline and add booking rule tests`

Acceptance:
- Commit contains code/infrastructure/test changes from this session.
- No secrets committed.

### Step B: Next functional backend task (Completed 2026-02-23)
Proposed next task:
- Implement booking-to-lesson synchronization so domain flow is complete:
  - on booking confirm => create lesson record (if not exists),
  - on booking cancel/reschedule => keep lesson state consistent,
  - emit outbox events for lesson lifecycle changes.

Why this task:
- It directly connects already-built booking and lessons domains into one coherent platform workflow.
- It unlocks realistic end-to-end scenarios for students/teachers.

Acceptance:
- Confirmed booking produces exactly one lesson.
- Cancel/reschedule does not leave orphaned or conflicting lessons.
- Outbox contains expected integration events.

### Step C: Integration tests over docker environment (booking/billing) (Completed 2026-02-23)
Goal: verify real HTTP + DB behavior, not only unit logic.

Minimum integration suite:
1. Student hold + confirm booking decrements package lessons.
2. Cancel >24h returns lesson.
3. Cancel <24h does not return lesson.
4. Reschedule keeps package lesson balance correct and links bookings.
5. Hold expiration endpoint releases stale slot.

Execution mode:
- Run tests against the dockerized app/db stack.
- Prefer dedicated test data setup/teardown per scenario.

Acceptance:
- Green integration test run in docker environment.
- Test scenarios match documented business rules.

## 9) Full Platform Roadmap (Execution Backbone)

### Phase 0: Stable baseline
Status: completed (2026-02-23).

### Phase 1: Core domain coherence
Status: completed (2026-02-23).
- Booking <-> Lessons lifecycle integration.
- Outbox event consistency for booking/lesson flows.
- Idempotency guards for critical transitions.

### Phase 2: Billing hardening
Status: completed (2026-02-23).
- Payment status workflows + reconciliation paths. (completed)
- Package expiration job/logic and edge-case handling. (completed)
- Better audit coverage for financial actions. (completed)

### Phase 3: Notifications pipeline
- Status: completed (2026-02-23).
- Outbox consumer/worker for notification dispatch. (completed)
- Retries/backoff/dead-letter strategy for failed sends. (completed)
- Delivery status observability. (completed)

### Phase 4: Admin and operations
- Status: completed (2026-02-23).
- Admin read models for bookings/payments/lessons KPIs. (completed)
- Auditable admin actions with traceability. (completed)
- Operational endpoints and runbooks. (completed)

### Phase 5: Production readiness
Status: completed (2026-02-23).
- CI (lint + unit + integration + migration checks). (completed)
- Security hardening (auth policies, secret handling, rate limits). (completed)
- Deployment baseline, monitoring, backup/restore strategy. (completed)

## 10) Definition of Done for "Platform MVP"
- Roles/auth flows work for student/teacher/admin.
- Teacher availability -> booking -> lesson lifecycle is coherent.
- Billing package balance is correct across hold/confirm/cancel/reschedule.
- Notification pipeline processes outbox events reliably.
- Audit logs and outbox provide traceability for critical actions.
- Integration tests cover main business scenarios and run in CI.
- Docker local runbook is stable and documented.

## 11) Progress Update (2026-02-23)
- Step B (booking <-> lesson synchronization) completed:
  - booking confirmation creates lesson if missing,
  - booking cancel/reschedule cancels linked lesson,
  - outbox emits `lesson.created` / `lesson.canceled`.
  - commit: `c03f3d1`.
- Step C (integration tests in dockerized environment) completed:
  - added `tests/test_booking_billing_integration.py` with 5 scenarios:
    1. hold + confirm decrements package lessons,
    2. cancel >24h returns lesson,
    3. cancel <24h does not return lesson,
    4. reschedule keeps balance and links bookings,
    5. hold expiration releases slot.
  - verified against running Docker stack: `5 passed`.
  - full test suite status: `10 passed`.
- Runtime auth risk resolved:
  - fixed `passlib+bcrypt` incompatibility by pinning `bcrypt=4.0.1` in `pyproject.toml`/`poetry.lock`.
  - verified `/api/v1/identity/auth/register` returns `201` in dockerized app after rebuild.
  - integration tests now use real `register + login` flow again.
- Phase 1 idempotency guards completed:
  - `confirm_booking` is idempotent for already `CONFIRMED` bookings (no double package consumption).
  - `cancel_booking` is idempotent for already `CANCELED` bookings.
  - `reschedule_booking` returns existing successor booking on retry.
  - covered by new unit tests in `tests/test_booking_rules.py`.
- Phase 2 payment workflow hardening (partial):
  - `billing.update_payment_status` now enforces valid transitions:
    - `pending -> succeeded/failed`
    - `failed -> pending/succeeded` (reconciliation retry path)
    - `succeeded -> refunded`
  - status update is idempotent when target status equals current status.
  - `paid_at` is set on first success and preserved on refund.
  - covered by `tests/test_billing_payment_rules.py` (6 tests).
- Phase 2 financial audit/outbox coverage (partial):
  - billing service now writes audit logs and outbox events for:
    - package creation,
    - payment creation,
    - payment status updates.
- Phase 2 package expiration handling (partial):
  - added admin endpoint `POST /api/v1/billing/packages/expire` to expire overdue active packages.
  - `BillingService.get_active_package` now persists `EXPIRED` status when an active package is already past `expires_at`.
  - covered by additional billing unit tests.
- CI bootstrap completed (partial):
  - added GitHub Actions workflow `.github/workflows/ci.yml`.
  - workflow installs dependencies via Poetry and runs `pytest -q` on push/PR.
- Phase 3 notifications worker (partial):
  - added outbox worker core: `app/modules/notifications/outbox_worker.py`.
  - added executable worker runner: `app/workers/outbox_notifications_worker.py`.
  - worker behavior:
    - processes pending outbox events into `notifications` records and marks them `SENT`,
    - requeues retryable failed outbox events with exponential backoff,
    - keeps terminal failures in `FAILED` state as dead-letter.
  - audit repository now supports:
    - listing retryable failed outbox events,
    - moving failed event back to pending.
  - covered by `tests/test_outbox_notifications_worker.py`.
- Phase 3 delivery observability completed:
  - added admin endpoint `GET /api/v1/notifications/delivery/metrics`.
  - endpoint returns:
    - notification status counters (`pending/sent/failed` + total),
    - outbox counters (`pending/processed/failed` + total),
    - retryable failed vs dead-letter failed outbox counts (`max_retries` aware).
  - added coverage in `tests/test_notifications_delivery_metrics.py`.
- Phase 2 billing hardening completed:
  - added package auto-expiration helper with consistent audit/outbox emission:
    - used by `get_active_package`,
    - used by `create_payment`,
    - used by `expire_packages`.
  - improved payment creation guards:
    - payment is rejected for expired packages,
    - payment is rejected for non-active packages.
  - expanded reconciliation/edge-case unit coverage in `tests/test_billing_payment_rules.py`:
    - `failed -> succeeded` sets `paid_at`,
    - transitions from `refunded` are rejected,
    - expired package checks emit `billing.package.expired`,
    - payment creation against inactive package has no side effects.
  - latest local suite status: `34 passed`.
- Phase 4 admin KPI read model (partial):
  - added endpoint `GET /api/v1/admin/kpi/overview` (admin-only).
  - KPI snapshot includes aggregated counters for:
    - users (by role),
    - bookings (by lifecycle status),
    - lessons (by status),
    - payments (by status + succeeded/refunded/net amounts),
    - lesson packages (by status).
  - traceability:
    - each KPI view writes `admin.kpi.view` action into `admin_actions`.
  - covered by `tests/test_admin_kpi_overview.py`.
  - latest local suite status: `36 passed`.
- Phase 5 CI hardening (partial):
  - updated `.github/workflows/ci.yml` with separate jobs:
    - `lint` (`ruff check app tests`),
    - `test` (`pytest -q`),
    - `migration` (`alembic upgrade head` against PostgreSQL service),
    - `integration` (run API + `tests/test_booking_billing_integration.py`).
  - repo-wide lint baseline is enforced in CI.
- Phase 4 operational overview endpoint (partial):
  - added endpoint `GET /api/v1/admin/ops/overview?max_retries=5` (admin-only).
  - operational snapshot includes:
    - outbox pending count,
    - retryable failed and dead-letter failed outbox counts,
    - failed notifications count,
    - stale booking holds count,
    - overdue active packages count.
  - traceability:
    - each ops overview read writes `admin.ops.view` action into `admin_actions`.
  - covered by `tests/test_admin_operations_overview.py`.
  - latest local suite status: `38 passed`.
- Phase 4 operations runbook completed:
  - added `README.md` runbook section for:
    - KPI overview check,
    - operations overview check,
    - hold/package remediation actions,
    - dead-letter handling guidance.
- Phase 5 security hardening (partial):
  - added production guard for default secret:
    - `Settings` now rejects placeholder `SECRET_KEY` values matching `change-me*`
      when `APP_ENV` is `production`/`prod`.
  - added production guard for process-local auth limiter:
    - startup requires `AUTH_RATE_LIMIT_ALLOW_IN_MEMORY_IN_PRODUCTION=true`
      in `production`/`prod` when `AUTH_RATE_LIMIT_BACKEND=memory`.
  - covered by `tests/test_config_security.py`.
  - latest local suite status: `41 passed`.
- Phase 5 auth rate limiting hardening (completed):
  - added in-memory sliding-window limiter core: `app/core/rate_limit.py`.
  - added Redis-backed shared sliding-window limiter backend in `app/core/rate_limit.py`.
  - limiter backend now selected by env:
    - `AUTH_RATE_LIMIT_BACKEND` (`memory`/`redis`),
    - `AUTH_RATE_LIMIT_REDIS_NAMESPACE`.
  - added per-IP guards for identity endpoints:
    - `POST /api/v1/identity/auth/register`,
    - `POST /api/v1/identity/auth/login`,
    - `POST /api/v1/identity/auth/refresh`.
  - configurable via env:
    - `AUTH_RATE_LIMIT_WINDOW_SECONDS`,
    - `AUTH_RATE_LIMIT_REGISTER_REQUESTS`,
    - `AUTH_RATE_LIMIT_LOGIN_REQUESTS`,
    - `AUTH_RATE_LIMIT_REFRESH_REQUESTS`,
    - `AUTH_RATE_LIMIT_TRUSTED_PROXY_IPS`.
  - `X-Forwarded-For` is trusted only when direct client IP is in
    `AUTH_RATE_LIMIT_TRUSTED_PROXY_IPS`.
  - rate-limit violations return unified app error:
    - code: `rate_limited`, HTTP: `429`.
  - covered by:
    - `tests/test_rate_limiter.py`,
    - `tests/test_identity_rate_limit.py`.
  - integration suite adapted for realistic proxy-IP simulation in auth registration helper.
  - latest local suite status: `46 passed`.
- Phase 5 deployment baseline and recovery strategy (partial):
  - added readiness probe endpoint:
    - `GET /ready` checks live DB connectivity (`SELECT 1`) and returns `503` on failure.
  - added Prometheus metrics endpoint:
    - `GET /metrics` exposes HTTP request counters/latency in Prometheus format.
  - covered by `tests/test_health_readiness.py`.
  - covered by `tests/test_metrics_observability.py`.
  - added backup/restore scripts for dockerized PostgreSQL:
    - `scripts/db_backup.ps1`,
    - `scripts/db_restore.ps1`.
  - updated `README.md` with:
    - liveness/readiness probe usage,
    - backup/restore operational commands.
  - added deployment baseline compose profile: `docker-compose.prod.yml`:
    - `db`,
    - `redis`,
    - `app`,
    - `outbox-worker`,
    - `prometheus`,
    - `alertmanager`,
    - `grafana`.
  - updated `README.md` with production compose bring-up and migration command.
  - latest local suite status: `48 passed`.
- Repo-wide style baseline completed:
  - `ruff check app tests` is now green locally.
  - CI lint job switched from scoped files to full `app/tests` check.
- Structural hardening follow-up completed:
  - production secret guard now rejects placeholder patterns `change-me*` (not only exact `change-me`).
  - production startup now requires explicit acknowledgement of process-local limiter:
    - `AUTH_RATE_LIMIT_ALLOW_IN_MEMORY_IN_PRODUCTION=true` (for memory backend in prod).
  - identity IP resolution now trusts `X-Forwarded-For` only for configured proxy sources:
    - `AUTH_RATE_LIMIT_TRUSTED_PROXY_IPS`.
  - integration suite setup was stabilized against auth-rate-limiter collisions:
    - shared cached auth users are created once per run in `tests/test_booking_billing_integration.py`.
  - CI integration job now sets `AUTH_RATE_LIMIT_TRUSTED_PROXY_IPS=127.0.0.1,::1` when starting API.
  - `scripts/db_restore.ps1` now streams backup content to `psql` instead of loading full SQL dump in memory.
  - latest local suite status: `51 passed`.
- Shared limiter follow-up completed:
  - added Redis runtime dependency (`redis`) and backend selector tests in `tests/test_rate_limiter.py`.
  - production config validation now enforces:
    - `REDIS_URL` is required when `AUTH_RATE_LIMIT_BACKEND=redis`,
    - in-memory explicit ack is required only for memory backend in `production`/`prod`.
  - `docker-compose.prod.yml` now includes `redis` service and defaults app/worker limiter backend to Redis.
  - `README.md` and `.env.example` updated with Redis limiter configuration.
  - latest local suite status: `56 passed`.
- Monitoring baseline follow-up completed:
  - added Prometheus instrumentation middleware and endpoint:
    - `app/core/metrics.py`,
    - `GET /metrics` in `app/main.py`.
  - production compose now includes Prometheus service with scrape config:
    - `ops/prometheus/prometheus.yml`,
    - `docker-compose.prod.yml` (`prometheus` on `9090`).
  - `README.md` updated with metrics/Prometheus usage.
  - latest local suite status: `53 passed, 5 skipped` (`tests/test_booking_billing_integration.py` skipped because local integration stack was unavailable).
- Monitoring dashboards and alert-routing follow-up completed:
  - added Prometheus alert rules baseline:
    - `ops/prometheus/alerts.yml` (`API down`, `high 5xx ratio`, `high p95 latency`).
  - added Alertmanager baseline config:
    - `ops/alertmanager/alertmanager.yml`.
  - added Grafana provisioning and dashboard baseline:
    - `ops/grafana/provisioning/datasources/prometheus.yml`,
    - `ops/grafana/provisioning/dashboards/dashboards.yml`,
    - `ops/grafana/dashboards/guitaronline-api-overview.json`.
  - updated production compose and env/docs:
    - `docker-compose.prod.yml` now runs `alertmanager` (`9093`) and `grafana` (`3000`),
    - `.env.example` includes `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`,
    - `README.md` includes monitoring stack usage and endpoints.
  - latest local suite status: `53 passed, 5 skipped` (`tests/test_booking_billing_integration.py` skipped because local integration stack was unavailable).
- Docker pull resilience follow-up completed:
  - added warmup script with retry/backoff for core runtime images:
    - `scripts/docker_warmup.ps1`.
  - added cache portability scripts for offline image reuse:
    - `scripts/docker_cache_export.ps1`,
    - `scripts/docker_cache_import.ps1`.
  - production compose now uses `pull_policy: if_not_present` for external image services
    (`db`, `redis`, `prometheus`, `alertmanager`, `grafana`).
  - `README.md` updated with warmup/cache/network mitigation runbook.
- Ops config validation follow-up completed:
  - added local validation script:
    - `scripts/validate_ops_configs.ps1`.
  - CI now validates ops configs in dedicated `ops-config` job:
    - `docker compose -f docker-compose.prod.yml config -q`,
    - `promtool check config` + `promtool check rules`,
    - `amtool check-config` for Alertmanager.
  - `README.md` updated with ops config validation runbook.
- Integration test runtime hardening follow-up completed:
  - `tests/test_booking_billing_integration.py` now caches stack health probe result,
    so when local stack is unavailable tests skip quickly without repeating full timeout per test.
  - current local measurement:
    - `tests/test_booking_billing_integration.py` completes as `5 skipped` in ~`3.6s`
      when `INTEGRATION_HEALTH_URL` is unavailable.
- Alert receiver onboarding follow-up completed:
  - added receiver template for Slack/PagerDuty/email:
    - `ops/alertmanager/alertmanager.receivers.example.yml`.
  - `README.md` now documents receiver onboarding flow.
- Root UX baseline follow-up completed:
  - added start landing page endpoint:
    - `GET /` now returns HTML navigation page (docs/health/ready/metrics),
    - reduces "folder listing" impression when opening service root.
  - covered by `tests/test_landing_page.py`.
- Live Server root helper follow-up completed:
  - added static root page for VS Code `Go Live` usage:
    - `index.html` at repo root (`http://127.0.0.1:5500/`),
    - includes quick links to API endpoints on `127.0.0.1:8000`.
  - updated `README.md` quick-start links.
- Russian UI localization follow-up completed:
  - translated user-facing texts to Russian for:
    - API landing page (`GET /`) in `app/main.py`,
    - VS Code Live Server helper page `index.html`.
  - updated landing-page test coverage in `tests/test_landing_page.py`.
- Frontend MVP portal follow-up completed:
  - added backend-served frontend portal at `GET /portal` with static assets at `/portal/static/*`:
    - `app/frontend/index.html`,
    - `app/frontend/static/styles.css`,
    - `app/frontend/static/app.js`.
  - implemented portal flows:
    - register/login (JWT),
    - profile (`/api/v1/identity/users/me`),
    - open slots (`/api/v1/scheduling/slots/open`),
    - my bookings (`/api/v1/booking/my`),
    - my packages for student role (`/api/v1/billing/packages/students/{id}`).
  - root landing and Go Live helper now include direct link to `/portal`.
  - covered by `tests/test_portal_page.py` and updated `tests/test_landing_page.py`.

## 12) Continuation Queue To Project Completion (Strict Order)

Execution rule:
- Start each next step only after previous step is fully completed and committed.

### Queue 1: Frontend MVP functional completion (Completed 2026-02-24)
Goal:
- Finish core user flow directly in `/portal` UI.

Tasks:
1. Add booking actions in portal for student flow:
   - hold booking,
   - confirm held booking,
   - cancel booking,
   - reschedule booking.
2. Add role-aware sections:
   - student (bookings/packages),
   - admin (package expiration + holds expiration action triggers),
   - teacher (my lessons view preparation via API already available).
3. Add robust API error rendering (validation/errors from backend) with Russian messages in UI.

Acceptance:
- End-to-end manual scenario from portal:
  registration/login -> hold -> confirm -> cancel/reschedule works.
- No console JS errors in browser during basic flow.

### Queue 2: Frontend security/session hardening (Completed 2026-02-24)
Goal:
- Make portal session behavior reliable and safe.

Tasks:
1. Add token-expiration handling UX:
   - auto refresh attempt once,
   - clear session + redirect to auth state on terminal auth failure.
2. Add minimal request concurrency guard for repeated clicks (double-submit protection).
3. Add logout-all-local-state cleanup and consistent status notifications.

Acceptance:
- Forced expired access token recovers via refresh or cleanly logs out without broken UI state.

### Queue 3: Portal integration test coverage (Completed 2026-02-24)
Goal:
- Prevent regressions in new `/portal` entrypoint and static delivery.

Tasks:
1. Add backend tests for static assets routing:
   - `/portal/static/styles.css`,
   - `/portal/static/app.js`.
2. Add auth flow API integration tests focused on portal-used endpoints sequence.
3. Keep existing suite runtime bounded for local runs.

Acceptance:
- New portal-related tests pass in CI.
- Existing tests remain green.

### Queue 4: Single-site runtime profile (Completed 2026-02-24)
Goal:
- Provide clean deployment topology where users open one base URL.

Tasks:
1. Add optional reverse-proxy profile (Nginx/Caddy) for:
   - `/` and `/portal` -> app,
   - `/api` passthrough to app API prefix.
2. Document canonical external URLs and health checks behind proxy.
3. Add compose validation for this profile.

Acceptance:
- Local/prod profile starts with one public entrypoint and working API/docs/portal routes.

### Queue 5: Demo data bootstrap (Completed 2026-02-24)
Goal:
- Make project demonstrable in a fresh environment quickly.

Tasks:
1. Add seed script for demo users/roles/teacher profile/slots/packages.
2. Add idempotent behavior and safe rerun semantics.
3. Document seed runbook and default demo credentials (non-production only).

Acceptance:
- Fresh DB + seed -> portal can be shown without manual data creation.

### Queue 6: External alert receivers onboarding (Completed 2026-02-25)
Goal:
- Close monitoring stack gap with real incident channels.

Tasks:
1. Configure real Alertmanager receivers (Slack/PagerDuty/SMTP) using environment secrets.
2. Add severity-based routing (`warning` vs `critical`).
3. Validate routing with synthetic alert firing.

Acceptance:
- Test alert is delivered to at least one real target channel.

### Queue 7: Release hardening and MVP closure (Completed 2026-02-25)
Goal:
- Finish project with release-grade baseline and handoff.

Tasks:
1. Final pass on README/runbooks to remove ambiguity and stale notes.
2. Add explicit release checklist (deploy, migrate, smoke tests, rollback).
3. Tag first stable release and snapshot final checkpoint.

Acceptance:
- Release checklist executed successfully on target environment.
- Checkpoint status switched to MVP closed.

## 13) Progress Update (2026-02-25)
- Queue 1 implementation delivered in portal frontend:
  - booking actions in UI (`hold`, `confirm`, `cancel`, `reschedule`),
  - role-aware tabs and sections for `student` / `teacher` / `admin`,
  - Russian-oriented API error rendering with validation path translation.
  - commits: `88cdc81`, `e72fbd6`.
- Queue 1 browser acceptance confirmed:
  - manual portal scenario completed: `registration/login -> hold -> confirm -> cancel/reschedule`,
  - no console JS errors reported during basic flow.
- Queue 3 delivered:
  - static assets routing tests added for:
    - `/portal/static/styles.css`,
    - `/portal/static/app.js`,
  - portal endpoint-sequence integration tests added with bounded runtime skip behavior when local stack is unavailable:
    - `tests/test_portal_auth_flow_integration.py`.
  - commit: `10240d6`.
- Queue 4 delivered:
  - optional reverse-proxy runtime profile:
    - `docker-compose.proxy.yml`,
    - `ops/nginx/default.conf`,
  - docs and validation script updated:
    - `README.md`,
    - `scripts/validate_ops_configs.ps1`.
  - commit: `35df422`.
- Queue 5 delivered:
  - idempotent demo seed script:
    - `scripts/seed_demo_data.py`,
  - runbook and demo credentials documented in `README.md`.
  - commit: `605d18b`.
- Queue 7 partial progress:
  - explicit release checklist added:
    - `ops/release_checklist.md`,
  - linked in `README.md`.
  - commit: `7138711`.
- Queue 2 completion and hardening finalization:
  - one-time token refresh retry on `401` is in portal API client,
  - terminal auth failure now forces clean auth-mode transition (`clearSession + showAuthMode`),
  - repeated click double-submit guard is applied to mutation buttons,
  - logout clears all local portal state and tokens.
- Queue 6 onboarding automation delivered:
  - added on-call Alertmanager config generator from env secrets:
    - `scripts/render_alertmanager_oncall_config.ps1`,
  - added alerting compose override profile:
    - `docker-compose.alerting.yml`,
  - added synthetic alert trigger script:
    - `scripts/alertmanager_fire_synthetic.ps1`,
  - updated docs/runbooks and env template for required `ALERTMANAGER_*` settings.
- Queue 6 acceptance confirmed (2026-02-25):
  - local `ALERTMANAGER_SLACK_WEBHOOK_URL` / `ALERTMANAGER_SLACK_CHANNEL` configured,
  - on-call Alertmanager config generated and loaded after restart,
  - synthetic alerts were delivered to Slack with working `<!channel>` mention.
- Queue 7 docs/runbook final-pass progress:
  - clarified README release/alerting paths (baseline, proxy, alerting overrides),
  - extended release checklist with synthetic alert delivery validation step,
  - ops config validation now checks alerting override when generated on-call config exists.
- Queue 7 completion confirmed (2026-02-25):
  - final docs/runbook pass completed:
    - alert routing description in `README.md` synchronized with generator fallback behavior,
    - release backup/restore scripts fixed (`scripts/db_backup.ps1`, `scripts/db_restore.ps1`).
  - release checklist executed on local target environment:
    - stack up with `docker-compose.prod.yml` + `docker-compose.alerting.yml`,
    - migration check: `alembic current` => `20260219_0001 (head)`,
    - smoke checks passed for `/health`, `/ready`, `/docs`, `/metrics`, `/portal`,
      `/portal/static/app.js`, `/portal/static/styles.css`,
      and auth flow `register -> login -> /api/v1/identity/users/me`,
    - synthetic alert routing validated with unique run id `df50ebde5753`
      and Slack notifications counter increase (`2 -> 4`),
    - backup created and verified readable:
      `backups/guitaronline-20260225-120853.sql`,
    - ops config validation passed (`promtool`, `amtool`, compose config checks).
  - first stable release tag target set: `v1.0.0`.

## 14) Queue Verification Audit (2026-02-25)
- Queue 1 (`Completed`):
  - portal student booking actions are implemented in `app/frontend/static/app.js`:
    `hold`, `confirm`, `cancel`, `reschedule`,
  - role-aware sections and Russian error rendering are implemented,
  - manual browser acceptance marked as confirmed in this checkpoint update.
- Queue 2 (`Completed`):
  - token-expiration handling is implemented (`refresh` retry once),
  - terminal auth failure returns UI to auth mode without stale session state,
  - request concurrency guard exists via disabled action buttons during in-flight operations,
  - logout clears local session/tokens and resets portal state.
- Queue 3 (`Completed 2026-02-24`):
  - portal static route tests exist: `tests/test_portal_page.py`,
  - portal auth sequence integration tests exist: `tests/test_portal_auth_flow_integration.py`,
  - latest local checks:
    - `py -m poetry run pytest -q tests/test_portal_page.py` => `3 passed`,
    - `py -m poetry run pytest -q -rs tests/test_portal_auth_flow_integration.py` => `2 skipped` (local integration stack unavailable at `http://localhost:8000/health`).
- Queue 4 (`Completed 2026-02-24`):
  - proxy profile and config present: `docker-compose.proxy.yml`, `ops/nginx/default.conf`,
  - docs and validation flow are present in `README.md` and `scripts/validate_ops_configs.ps1`.
- Queue 5 (`Completed 2026-02-24`):
  - idempotent seed script present: `scripts/seed_demo_data.py`,
  - demo runbook and credentials documented in `README.md`.
- Queue 6 (`Completed 2026-02-25`):
  - onboarding automation exists:
    - `scripts/render_alertmanager_oncall_config.ps1`,
    - `docker-compose.alerting.yml`,
    - `scripts/alertmanager_fire_synthetic.ps1`,
  - receiver template exists: `ops/alertmanager/alertmanager.receivers.example.yml`,
  - severity routing and synthetic alert delivery were verified against Slack channel in local environment.
- Queue 7 (`Completed 2026-02-25`):
  - task 1 completed: final docs/runbooks pass done and stale ambiguity removed,
  - task 2 completed: explicit release checklist exists and was executed,
  - task 3 completed: stable release tagged (`v1.0.0`) with final checkpoint snapshot.

## 15) Post-MVP Hardening Backlog
Execution order:
2 -> 3 -> 4 -> 5 -> 1

2. One-click deploy pipeline (`Completed 2026-02-25`)
   - workflow added: `.github/workflows/deploy.yml` (`workflow_dispatch`, confirm gate; optional push-to-main auto mode with `AUTO_DEPLOY_ENABLED=true`),
   - automated remote deploy script added: `scripts/deploy_remote.sh`,
   - post-deploy smoke checks extracted: `scripts/deploy_smoke_check.py`,
   - docs updated: `README.md`, `ops/release_checklist.md`.

3. Repository secret leak prevention (`Completed 2026-02-25`)
   - CI guardrails added in `.github/workflows/ci.yml`:
     - tracked `.env` hard-fail check,
     - repository secret scan via `scripts/secret_guard.py --mode repo`,
   - local pre-commit guardrails added:
     - `.githooks/pre-commit`,
     - `scripts/install_git_hooks.ps1`,
   - docs updated: `README.md`.

4. Monitoring noise control and routing hardening (`Completed 2026-02-25`)
   - alert labeling hardened in `ops/prometheus/alerts.yml` (`service=guitaronline-api`),
   - baseline and generated Alertmanager configs now include inhibit rules and tuned warning/critical repeat behavior:
     - `ops/alertmanager/alertmanager.yml`,
     - `scripts/render_alertmanager_oncall_config.ps1`,
   - maintenance silence baseline added:
     - `scripts/alertmanager_create_silence.ps1`,
     - `scripts/alertmanager_expire_silence.ps1`,
   - docs/runbook updated and validated:
     - `README.md`,
     - `ops/release_checklist.md`,
     - `scripts/validate_ops_configs.ps1` run passed.

5. Backup/restore verification automation (`Completed 2026-02-25`)
   - reproducible restore verification scripts added:
     - `scripts/verify_backup_restore.sh` (artifact-aware local/host verification),
     - `scripts/verify_backup_remote.sh` (remote orchestration wrapper),
   - recurring automation added:
     - `.github/workflows/backup-restore-verify.yml` (scheduled + manual verify),
   - runbook/docs updated:
     - `README.md`,
     - `ops/release_checklist.md`.

1. Secure `.env` delivery to server without storing secrets in git (`Completed 2026-02-25`)
   - source: CI/CD secrets,
   - deploy: write `.env` on target host before compose up,
   - control: `.env` never tracked in git history,
   - implemented via:
     - one-click deploy upload from `PROD_ENV_FILE_B64` in `.github/workflows/deploy.yml`,
     - tracked `.env` CI guard in `.github/workflows/ci.yml`,
     - helper for secret preparation: `scripts/encode_env_base64.ps1`,
     - docs updates in `README.md` and `ops/release_checklist.md`.
## 16) MVP Closure Status
- Checkpoint status: MVP closed (2026-02-25).


## 17) Next Session Handover (Priority Plan For 2026-02-26)

Objective for next session:
- Complete first successful remote GitHub Actions cycle:
  1. `deploy` workflow success,
  2. `backup-restore-verify` workflow success on same ref.

Current confirmed state before stopping:
- branch: `main`,
- latest commit with hardening backlog: `63f00fc`,
- push status: `origin/main` updated,
- local working tree was clean after push,
- workflows and scripts are already in repository:
  - `.github/workflows/deploy.yml`,
  - `.github/workflows/backup-restore-verify.yml`,
  - `scripts/deploy_remote.sh`,
  - `scripts/deploy_smoke_check.py`,
  - `scripts/verify_backup_remote.sh`,
  - `scripts/verify_backup_restore.sh`,
  - `scripts/secret_guard.py`.

### P0 (Highest Priority): Secrets + SSH Preconditions

Do this first, otherwise workflows will fail immediately.

Required GitHub repository secrets for `deploy`:
- `DEPLOY_HOST`:
  - purpose: target server host/IP for SSH,
  - expected format: `144.31.77.239`.
- `DEPLOY_USER`:
  - purpose: SSH user used by Actions runner,
  - expected format: linux account name, e.g. `deploy` / `ubuntu`.
- `DEPLOY_PATH`:
  - purpose: absolute project path on server where `.git` exists,
  - expected format: `/opt/guitaronline`.
- `DEPLOY_SSH_PRIVATE_KEY`:
  - purpose: private SSH key for authentication,
  - expected format: full multiline OpenSSH private key (`-----BEGIN OPENSSH PRIVATE KEY----- ...`).
- `PROD_ENV_FILE_B64`:
  - purpose: production `.env` payload uploaded during deploy,
  - expected format: base64 string generated from `.env`.

Required GitHub repository secrets for `backup-restore-verify`:
- `DEPLOY_HOST`,
- `DEPLOY_USER`,
- `DEPLOY_PATH`,
- `DEPLOY_SSH_PRIVATE_KEY`.

Optional but recommended:
- `DEPLOY_PORT`:
  - default fallback is `22`,
  - set only if SSH runs on a non-standard port.
- `DEPLOY_KNOWN_HOSTS`:
  - recommended for host key pinning,
  - if absent, workflow uses `ssh-keyscan`.

Host-side prerequisites to verify once:
1. `DEPLOY_PATH` exists (or can be created) and is writable by `DEPLOY_USER`.
2. SSH public key (from `DEPLOY_SSH_PRIVATE_KEY`) is in `~/.ssh/authorized_keys` for `DEPLOY_USER`.
3. `DEPLOY_USER` can run `docker compose` on target host.
4. `git` is installed on host; workflow bootstrap will initialize repo metadata and configure `origin` automatically when `.git` is missing.

### P1: Run Deploy Workflow

Workflow start:
1. GitHub -> `Actions` -> `deploy` -> `Run workflow`.
2. Inputs:
   - `ref=main`,
   - `profile=standard` (or `proxy` if reverse-proxy profile is needed),
   - `run_backup=true`,
   - `run_smoke=true`,
   - `confirm=DEPLOY`.

Expected behavior:
1. Validates required secrets.
2. Connects via SSH.
3. Decodes `PROD_ENV_FILE_B64` and writes `${DEPLOY_PATH}/.env`.
4. Runs remote deploy script:
   - bootstrap repo metadata when target path has no `.git`,
   - `git fetch/checkout`,
   - optional pre-deploy DB backup,
   - `docker compose up --build -d`,
   - `alembic upgrade head`,
   - smoke tests.
5. If failure occurs after checkout, rollback trap attempts return to previous SHA.

Deploy success criteria:
- workflow job status `Success`,
- step `Deploy, migrate, smoke, rollback on failure` is green,
- logs contain `Deployment completed successfully.`.

### P2: Run Backup/Restore Verification Workflow

Run only after successful deploy:
1. GitHub -> `Actions` -> `backup-restore-verify` -> `Run workflow`.
2. Inputs:
   - `ref` same as deploy ref,
   - `keep_backup=true` (or `false` if no artifact retention needed),
   - `confirm=VERIFY`.

Expected behavior:
- connects to same host/path,
- executes `scripts/verify_backup_restore.sh`,
- creates verification DB, restores backup, checks public tables count,
- reports pass/fail in workflow logs.

Verification success criteria:
- workflow job status `Success`,
- logs contain `Backup/restore verification passed.`.

### P3: Post-Run Evidence Capture (Do Not Skip)

After both workflows are green, record in this checkpoint:
1. deploy workflow run URL/id and timestamp,
2. backup-restore-verify run URL/id and timestamp,
3. deployed ref/SHA,
4. profile used (`standard` or `proxy`),
5. whether `keep_backup` was true/false.

Execution evidence (recorded 2026-02-26, UTC):
- deploy:
  - run id: `22431343056`,
  - run URL: `https://github.com/HiMRS-dev/GuitarOnline/actions/runs/22431343056`,
  - created: `2026-02-26T06:55:34Z`,
  - completed: `2026-02-26T06:55:52Z`,
  - conclusion: `success`.
- backup-restore-verify:
  - run id: `22431359500`,
  - run URL: `https://github.com/HiMRS-dev/GuitarOnline/actions/runs/22431359500`,
  - created: `2026-02-26T06:56:11Z`,
  - completed: `2026-02-26T06:56:29Z`,
  - conclusion: `success`.
- deployed ref/SHA:
  - `ref=main`,
  - `sha=760559859fe05934fe4f604b192d5b87c376b4fe`.
- deploy profile: `standard`.
- backup verification `keep_backup=true`.

Auto-deploy follow-up evidence (recorded 2026-02-26, UTC):
- auto mode control:
  - repository secret `AUTO_DEPLOY_ENABLED=true` configured.
- first push-triggered run after enabling auto mode:
  - run id: `22431491059`,
  - run URL: `https://github.com/HiMRS-dev/GuitarOnline/actions/runs/22431491059`,
  - event: `push`,
  - conclusion: `failure` (workflow-definition issue; no jobs started).
- corrected push-triggered run after guard fix:
  - run id: `22431548611`,
  - run URL: `https://github.com/HiMRS-dev/GuitarOnline/actions/runs/22431548611`,
  - event: `push`,
  - created: `2026-02-26T07:03:22Z`,
  - completed: `2026-02-26T07:03:46Z`,
  - conclusion: `success`,
  - deployed sha: `979fbd796d034c5c12d975519e6ae5e9b1dc1a0a`.

Reality reconciliation (validated 2026-02-26, UTC):
- original "next session" handover objective is completed.
- latest push-triggered deploy run:
  - run id: `22431967798`,
  - run URL: `https://github.com/HiMRS-dev/GuitarOnline/actions/runs/22431967798`,
  - event: `push`,
  - created: `2026-02-26T07:18:59Z`,
  - completed: `2026-02-26T07:19:16Z`,
  - conclusion: `success`,
  - deployed sha: `708e94976801f21023dba113aad7ef3a746507e7`.
- latest backup-restore verification run:
  - run id: `22431359500`,
  - run URL: `https://github.com/HiMRS-dev/GuitarOnline/actions/runs/22431359500`,
  - event: `workflow_dispatch`,
  - created: `2026-02-26T06:56:11Z`,
  - completed: `2026-02-26T06:56:29Z`,
  - conclusion: `success`.
- server runtime verification snapshot:
  - host git state: `main` at `708e94976801f21023dba113aad7ef3a746507e7`,
  - core services (`app`, `db`, `redis`, `outbox-worker`, `prometheus`, `alertmanager`, `grafana`) are `Up`,
  - health/readiness checks: `/health=ok`, `/ready=ready`,
  - `scripts/deploy_smoke_check.py` passed on host.
- remaining actionable items in this checkpoint:
  - no mandatory unfinished execution items,
  - only non-blocking risks/technical debt listed in section 6.

### Fast Failure Triage Map (Use In Order)

If error is `Missing required repository secret: DEPLOY_HOST`:
- add/update secret `DEPLOY_HOST` in repo Actions secrets.

If error is `Permission denied (publickey)`:
- wrong/missing private key in `DEPLOY_SSH_PRIVATE_KEY`,
- public key not installed for `DEPLOY_USER`,
- wrong `DEPLOY_USER`.

If error is `Deploy path is not writable`:
- wrong owner/permissions for `DEPLOY_PATH`,
- `DEPLOY_USER` cannot write to target directory.

If error is `docker compose: command not found` or permission issues:
- docker/compose missing on host or user lacks docker permissions.

If smoke checks fail:
- inspect service logs on host (`app`, `db`, `outbox-worker`),
- rerun deploy after fix (rollback already attempted by script).

### Resume Shortcut (Historical, Completed 2026-02-26)
1. Verify secrets in GitHub UI (`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`, `DEPLOY_SSH_PRIVATE_KEY`, `PROD_ENV_FILE_B64`).
2. Run `deploy` workflow with `confirm=DEPLOY`.
3. If green, run `backup-restore-verify` with `confirm=VERIFY`.

## 18) Backlog Intake: Admin+Calendar First (Received 2026-03-04)

Intake source:
- user-provided `Backlog v1 (Admin+Calendar first)`, items `A1`-`A10`.

Review status labels:
- `ready` = aligns with current codebase, low migration risk.
- `partial` = base already exists, needs extension/hardening.
- `decision_required` = meaningful conflict/breaking-change risk; resolve first.

### A1. Base admin API contract DTOs + UTC timestamp naming
Status: `decision_required`
- Existing DTOs already cover `Teacher`, `Slot`, `Booking`, `Package`, `Lesson`, and `Student` via `identity.UserRead`.
- Current field naming uses `start_at`, `end_at`, `created_at`, `updated_at`, etc., not strict `*_at_utc`.
- Renaming response fields to `*_at_utc` can break:
  - frontend portal consumer (`app/frontend/static/app.js`),
  - integration tests that assert current payload keys.
- `docs/ADMIN_API.md` does not exist yet and can be added.

### A2. Standardized API errors
Status: `partial`
- Global error envelope already exists as `{ "error": { "code": "...", "message": "..." } }`.
- Missing target format part: `details`.
- Validation error shape from FastAPI should be explicitly normalized into the same contract.

### A3. Strict RBAC rules
Status: `decision_required`
- `/api/v1/admin/*` is currently admin-only at service layer.
- Strict requirement "all teacher endpoints only teacher / all student endpoints only student" conflicts with current behavior:
  - teacher profile operations allow `admin` or owner,
  - lesson operations allow `admin` + `teacher`,
  - some booking operations are accessible by role-context owner/admin.
- Explicit 401/403 endpoint tests for deny paths are not yet a dedicated suite.

### A4. CORS + frontend env
Status: `decision_required`
- CORS middleware is not configured in `app/main.py`.
- `DATABASE_URL` already exists.
- Requested `JWT_SECRET` conflicts with current canonical `SECRET_KEY` usage in config/security/tests.
- Safe path likely requires alias/backward compatibility rather than direct rename.

### A5. Dev seed data
Status: `partial`
- Existing script: `scripts/seed_demo_data.py` (idempotent, documented in README).
- Current baseline generates demo users and slots/packages, but not requested exact distribution:
  - requested: `1 admin, 3 teacher, 5 student, 2 package, 10 slots`.
- Requires expanding existing seeder, not greenfield creation.

### A6. OpenAPI/Swagger admin-friendly polish
Status: `partial`
- Tags/descriptions already present across routers.
- Examples are limited and can be enriched.
- API endpoints are documented; intentionally hidden non-API routes (`/`, `/portal`, `/metrics`) are out of schema.

### A7. Audit log for admin actions
Status: `partial`
- `audit_logs` and `admin_actions` tables/services already exist.
- Additional coverage required for explicit events:
  - verify teacher,
  - bulk-create slots,
  - block slot,
  - cancel booking.
- Some of these imply new endpoints/use-cases (e.g., bulk-create slots, block slot) before audit wiring.

### A8. Validate all dates in UTC
Status: `partial`
- `ensure_utc(dt)` already exists in `app/shared/utils.py`.
- It is already used in key services (`scheduling`, `billing`, `lessons`), but not yet enforced as a formal cross-module rule.
- Edge-case timezone tests should be added (naive datetimes, non-UTC offsets, boundary cases).

### A9. Normalize statuses as enums
Status: `decision_required`
- Already normalized enums exist: `Slot`, `Booking`, `Package`, `Payment`, `Lesson`.
- Gap: no `TeacherStatusEnum`; teacher profile currently uses boolean `is_approved`.
- Introducing `TeacherStatusEnum` requires migration + schema/API updates + data mapping.

### A10. Single source of truth for Slot/Booking/Lesson
Status: `ready`
- Current implementation already aligns with target domain model:
  - `Slot` = availability,
  - `Booking` = reservation against slot,
  - `Lesson` = fact entity tied to booking lifecycle.
- Formalization file `docs/DOMAIN_RULES.md` is not present and can be added.

Execution note:
- Before implementation, resolve three architecture decisions to avoid rework:
  1. timestamp contract migration strategy (`*_at_utc` vs backward-compatible aliases),
  2. strict RBAC model boundaries (especially teacher/admin overlaps),
  3. teacher status model (`is_approved` boolean vs enum) and env naming (`SECRET_KEY`/`JWT_SECRET`).

## 19) Backlog v1.1 (Approved Rewrite, 2026-03-04)

Scope:
- rewrite conflict-prone items from `Backlog v1` into backward-compatible implementation tasks.

### A1 (rewritten): Admin API contracts + UTC field naming without breaking existing clients
- Introduce admin DTO contracts for `/api/v1/admin/*` with time fields in `*_at_utc` format (ISO8601 UTC).
- Do not rename existing `*_at` fields in already shipped endpoints at this stage.
- Add `docs/ADMIN_API.md` with:
  - example payloads,
  - field mapping table (`*_at` -> `*_at_utc`),
  - deprecation/migration plan.

### A3 (rewritten): RBAC matrix with explicit admin override
- Enforce:
  - `/admin/**` -> `admin` only.
  - teacher scenarios -> `teacher` (own resources) + explicit `admin` override.
  - student scenarios -> `student` (own resources) + explicit `admin` support path.
- Add endpoint-level HTTP tests for:
  - `401` (missing/invalid token),
  - `403` (role/resource forbidden),
  - `200/201` (allowed path).

### A4 (rewritten): CORS + env compatibility strategy
- Add CORS configuration using `FRONTEND_ADMIN_ORIGIN` (default `http://localhost:5173`).
- Keep `SECRET_KEY` as canonical JWT signing secret.
- Add `JWT_SECRET` as backward-compatible alias:
  - when set, it has priority over `SECRET_KEY`,
  - document precedence and migration guidance.
- Keep `DATABASE_URL` unchanged.

### A9 (rewritten): Teacher status migration in phases
- Keep current status enums for slot/booking/package/payment/lesson as-is.
- Introduce `TeacherStatusEnum` via phased migration:
  - add enum column for teacher status,
  - backfill mapping from `is_approved`:
    - `true` -> `verified`,
    - `false` -> `pending`,
  - keep `is_approved` backward-compatible during transition,
  - remove legacy boolean only after client migration completion.

### Governance
- Create ADR records before coding for A1/A3/A4/A9 to lock:
  - contract migration strategy,
  - RBAC boundaries,
  - secret key env precedence,
  - teacher status transition plan.

## 20) Epic B Intake: Scheduling Hardening (Received 2026-03-04)

Intake source:
- user-provided `Epic B — Scheduling (слоты) железно`, items `B1`-`B14`.

Review status labels:
- `ready` = aligns with current codebase, low migration risk.
- `partial` = base already exists, needs extension/hardening.
- `decision_required` = meaningful conflict/breaking-change risk; resolve first.

### B1. `GET /admin/teachers?status=&verified=&q=&tag=`
Status: `decision_required`
- Current admin module has no teacher-list endpoint.
- Existing teacher model has `is_approved`, but no `tags` and no dedicated `teacher_status` yet.
- Search by name/email is implementable, but depends on final status/tag model from A9 follow-up.

### B2. `GET /admin/teachers/{id}` (tags/status/verified)
Status: `decision_required`
- Current data model supports `verified` (`is_approved`) only.
- `tags` and explicit `status` are not yet modeled.

### B3. `POST /admin/teachers/{id}/verify` and `/disable` + audit
Status: `decision_required`
- Verify can map to `is_approved=true` today.
- Disable behavior is ambiguous in current model:
  - disable account via `users.is_active=false`, or
  - disable teacher capability via dedicated teacher status.
- Audit logging infrastructure exists, but action semantics must be finalized first.

### B4. `GET /admin/slots?teacher_id=&from_utc=&to_utc=` + aggregated booking status
Status: `partial`
- Current scheduling API exposes only open slots (`/scheduling/slots/open`) and no UTC range filter.
- New admin endpoint is feasible, but requires explicit mapping rules for aggregated status
  (`open/held/confirmed`) from `slot.status` + optional linked booking state.

### B5. `POST /admin/slots` (single slot create with strict validation)
Status: `partial`
- Existing `/scheduling/slots` already validates:
  - `start < end`,
  - not in the past,
  - admin-only access.
- Missing pieces:
  - minimum duration rule,
  - dedicated admin contract/path,
  - overlap guard integration.

### B6. `DELETE /admin/slots/{slot_id}` with confirmed-booking safeguard
Status: `decision_required`
- Current DB schema uses `bookings.slot_id` foreign key with `ondelete=RESTRICT`.
- Hard delete is blocked when any booking row references slot (not only confirmed).
- Requirement "forbidden only for CONFIRMED booking" conflicts with current relational constraints.

### B7. `POST /admin/slots/{slot_id}/block` with reason + audit
Status: `decision_required`
- Current slot statuses: `open/hold/booked/canceled`; no explicit `blocked` status.
- No dedicated `block_reason` field in slot model.
- Need decision:
  - treat block as `canceled` + reason in audit payload, or
  - introduce explicit blocked status/metadata via migration.

### B8. `POST /admin/slots/bulk-create` (base)
Status: `partial`
- No bulk-create endpoint exists yet.
- Core generation is feasible; needs overlap checks, deterministic skip reasons, and bounded transaction handling.

### B9. Bulk-create exceptions (`exclude_dates[]`, `exclude_time_ranges[]`)
Status: `partial`
- Natural extension of B8; no current implementation conflict.
- Requires clear UTC normalization and precedence rules (base ranges vs exclusions).

### B10. Service-level anti-overlap in transaction
Status: `partial`
- No anti-overlap guard exists now.
- Implementable in service layer with transactional create flow and conflict reporting.

### B11. DB-level anti-overlap (constraint or locking)
Status: `decision_required`
- No overlap constraint currently exists in schema/migrations.
- Requires design choice:
  - PostgreSQL exclusion constraint (higher rigor, heavier migration complexity), or
  - interval locking strategy (`SELECT ... FOR UPDATE`) as pragmatic fallback.

### B12. `GET /admin/slots/stats?from_utc&to_utc`
Status: `decision_required`
- Requested statuses: `open/held/confirmed/completed/cancelled` (canonical backend token: `canceled`).
- Current model spans multiple entities:
  - slot: `open/hold/booked/canceled`,
  - booking: `hold/confirmed/canceled/expired`,
  - lesson: `scheduled/completed/canceled`.
- Need explicit counting semantics to avoid inconsistent dashboards.

### B13. Automatic HOLD cleanup worker
Status: `partial`
- Manual expiration endpoint already exists: `POST /api/v1/booking/holds/expire` (admin-gated).
- No periodic hold-cleanup worker exists yet (only notifications outbox worker is deployed).
- Requires decision on execution identity and wiring:
  - system job path without user actor, or
  - technical admin actor strategy.

### B14. Integration test: bulk-create + no-overlap
Status: `ready`
- No direct conflict; depends on B8/B10/B11 contract finalization.

Cross-cutting risks to resolve before coding Epic B:
1. Teacher taxonomy for admin filters/cards (`status`, `verified`, `tags`) is not finalized.
2. Slot lifecycle semantics (`blocked` vs `canceled`) is not finalized.
3. Slot hard-delete policy conflicts with current `ondelete=RESTRICT` behavior.
4. Overlap strategy choice (service-only vs DB-backed) affects API guarantees and migration scope.
5. Existing schema constraint `bookings.slot_id` unique can block re-booking of the same slot after cancellation; this should be reviewed in scheduling lifecycle decisions.

## 21) Epic B v1.1 (Approved Decisions, 2026-03-04)

Decision scope:
- lock key architecture/contract choices for `B1`-`B14` before implementation.

1. Teacher identity key in admin scheduling flows:
- use `teacher_id = users.id` for admin endpoints and slot operations (not `teacher_profiles.id`).

2. Teacher status model:
- introduce `TeacherStatusEnum` with values: `pending`, `verified`, `disabled`.
- keep `is_approved` temporarily for backward compatibility during migration window.

3. Teacher tags model:
- store tags in dedicated relational table (`teacher_profile_tags`) instead of free-text/JSON blob.

4. Admin teacher list/details filters:
- in `GET /admin/teachers`, implement `q` over `teacher_profiles.display_name` + `users.email`.
- implement filters via joins for `status`, `verified`, `tag`.

5. Verify/disable semantics:
- `POST /admin/teachers/{id}/verify`:
  - set `teacher_status=verified`,
  - set `is_approved=true`.
- `POST /admin/teachers/{id}/disable`:
  - set `teacher_status=disabled`,
  - set `users.is_active=false`.
- both actions must write audit records in `audit_logs`.

6. Slot deletion policy:
- `DELETE /admin/slots/{slot_id}` is allowed only when slot has no related booking rows.
- if slot has any booking row, return `409` and require `POST /admin/slots/{slot_id}/block`.

7. Slot block semantics:
- introduce explicit slot status `blocked`.
- add slot metadata fields:
  - `block_reason`,
  - `blocked_at`,
  - `blocked_by_admin_id`.

8. Re-booking and active-booking uniqueness strategy:
- replace current unconditional `bookings.slot_id` uniqueness with active-state uniqueness policy,
  allowing re-booking after terminal statuses (`canceled`, `expired`).
- target behavior: only active booking states (`hold`, `confirmed`) must be unique per slot.

9. Anti-overlap protection strategy:
- apply two-layer protection:
  - service-layer overlap validation in transaction with deterministic conflict reasons,
  - locking with `SELECT ... FOR UPDATE` on candidate teacher interval range.
- DB exclusion constraint remains optional second-phase hardening.

10. Slot stats semantics (`GET /admin/slots/stats`):
- use single-final-bucket counting per slot with priority:
  - `completed > canceled > confirmed > held > open`.
- avoid double counting across slot/booking/lesson entities.

11. Automatic HOLD cleanup execution model:
- add dedicated periodic worker `booking_holds_expirer`.
- worker invokes system-level expiration path (`expire_holds_system()`), not user-token flow.

12. Integration guarantee for bulk create:
- keep mandatory integration scenario:
  - bulk-create schedule,
  - assert no overlapping intervals per teacher remain in DB.

## 22) Epic C Intake: Booking + 24h Policy (Received 2026-03-04)

Intake source:
- user-provided `Epic C — Booking (бронь) + правила 24 часа`, items `C1`-`C12`.
- items already fully covered by existing tests are intentionally excluded from checkpoint execution scope
  (`C11`, `C12`).
- notes in this intake section reflect pre-Epic-D accounting assumptions; for final booking/package
  accounting model, section `25) Epic D v1.1` is authoritative.

Review status labels:
- `ready` = aligns with current codebase, low migration risk.
- `partial` = base already exists, needs extension/hardening.
- `decision_required` = meaningful conflict/breaking-change risk; resolve first.

### C1. `GET /admin/bookings?teacher_id&student_id&status&from_utc&to_utc`
Status: `partial`
- Current booking API provides role-scoped listing only: `GET /booking/my`.
- Admin can currently list all bookings only indirectly via role behavior, without explicit admin endpoint/filters/range.

### C2. `POST /admin/bookings/{id}/cancel` (reason + who canceled + 24h policy)
Status: `partial`
- Core cancel logic and 24h refund behavior already exist in `BookingService.cancel_booking`.
- Missing dedicated admin endpoint and explicit actor trace (`who canceled`) in booking-facing contract;
  actor trace can be solved via audit log and/or model field decision.

### C3. `POST /admin/bookings/{id}/reschedule` (atomic cancel + new confirmed)
Status: `decision_required`
- Current reschedule flow already performs `cancel + hold + confirm` in one request transaction.
- But admin-initiated reschedule is blocked by current role guard:
  - `reschedule_booking` calls `hold_booking`,
  - `hold_booking` currently allows only `student`.
- Needs explicit admin/system reschedule path.

### C4. HOLD 10 minutes enforce + concurrency tests
Status: `partial`
- HOLD expiry is already enforced (`hold_expires_at = now + BOOKING_HOLD_MINUTES`).
- Slot is moved to `HOLD` at booking hold creation.
- Missing explicit concurrency test coverage for parallel HOLD attempts on same slot.

### C5. Confirm booking: reserve consumption and transaction
Status: `partial`
- Confirm path already checks package existence and `lessons_left > 0`, and consumes one lesson
  (current implementation baseline; target accounting model is superseded by section `25`).
- Booking is already linked to `package_id` from HOLD stage.
- Runs in request transaction, but no explicit documented transaction boundary for this business invariant yet.

### C6. No booking/reschedule in the past
Status: `partial`
- Hold flow already blocks past slots (`slot.start_at <= now`).
- Reschedule reuses hold flow, so past-slot check applies transitively.
- Should be explicitly documented/tested as a cross-flow invariant (including admin path once added).

### C7. Unified 24h policy function + boundary tests
Status: `partial`
- 24h decision is currently inline in `cancel_booking` via `hours_before_lesson > BOOKING_REFUND_WINDOW_HOURS`.
- No dedicated helper `can_refund_by_policy(now_utc, slot_start_utc)` yet.
- Boundary tests around exactly `24:00:00` are not isolated as policy-unit coverage.

### C8. Audit log for cancel/reschedule admin actions
Status: `partial`
- Current flow emits outbox events (`booking.canceled`, `booking.rescheduled`), but not explicit admin action audit entries for these operations.

### C9. Add `NO_SHOW` status
Status: `decision_required`
- No `NO_SHOW` status exists in current booking/lesson enums.
- Needs domain decision:
  - apply to booking, lesson, or both,
  - define billing/package consequence (legacy note referenced confirm-time consumption baseline).

### C10. Consistency: `slot_status` vs `booking_status`
Status: `decision_required`
- Current model stores lifecycle state in both slot and booking.
- Existing known risk remains: unconditional `bookings.slot_id` uniqueness can block re-booking after terminal states.
- Consistency rule should be finalized together with Epic B slot lifecycle decisions.

Cross-cutting notes for Epic C:
1. Endpoint naming mismatch to resolve in API contract:
   - current public prefix is `/booking/*`,
   - intake text uses `/bookings/*`.
2. Admin booking operations in C2/C3 should align with approved RBAC matrix (`admin` only for `/admin/**`).
3. C9/C10 should be decided in one design step with Epic B slot lifecycle and uniqueness policy to avoid double migration.

## 23) Epic C v1.1 (Approved Decisions, 2026-03-04)

Decision scope:
- lock implementation direction for unresolved Epic C items (`C1`-`C10`).
- explicitly exclude already covered test-only items (`C11`, `C12`) from checkpoint execution scope.

1. Booking endpoint contract split:
- keep public/user flows under existing prefix `/booking/*`.
- introduce admin-only booking operations under `/admin/bookings/*`.

2. Admin booking list endpoint (`C1`):
- implement `GET /admin/bookings` with pagination and filters:
  - `teacher_id`,
  - `student_id`,
  - `status`,
  - `from_utc`,
  - `to_utc`.
- filtering logic should be repository-level to keep service deterministic and testable.

3. Admin cancel endpoint (`C2`):
- implement `POST /admin/bookings/{id}/cancel` as admin wrapper over booking cancel core.
- require explicit `reason`.
- persist admin trace in audit layer (`admin_id`, `booking_id`, `reason`, effective refund decision).

4. Admin reschedule endpoint (`C3`):
- implement dedicated admin reschedule path (must not depend on student-only hold permission).
- execute atomically as one service transaction:
  - cancel old booking,
  - hold target slot,
  - confirm new booking,
  - set `rescheduled_from_booking_id`.

5. Unified 24h policy helper (`C7`):
- extract policy into:
  - `can_refund_by_policy(now_utc, slot_start_utc) -> bool`.
- use this helper from all cancel flows (student/admin/system).
- add strict boundary tests:
  - `23:59:59`,
  - `24:00:00`,
  - `24:00:01`.

6. HOLD concurrency hardening (`C4`):
- enforce slot-level concurrency control during HOLD creation (row lock on slot candidate).
- add integration scenario for concurrent HOLD attempts on same slot:
  - first HOLD succeeds,
  - second HOLD fails deterministically.

7. Confirm consistency and transaction invariants (`C5`, `C6`):
- keep invariant checks in confirm flow:
  - slot not in the past,
  - package active,
  - available package capacity > 0 (`lessons_left - lessons_reserved > 0` once Epic D accounting model is applied).
- keep confirm side-effects in same request transaction boundary.

8. Admin audit for cancel/reschedule (`C8`):
- add explicit admin audit actions:
  - `admin.booking.cancel`,
  - `admin.booking.reschedule`.
- include structured payload (`booking_id`, `old_slot_id`, `new_slot_id`, `reason`, actor id).

9. `NO_SHOW` domain placement (`C9`):
- add `NO_SHOW` to `LessonStatus` (not `BookingStatus`) to avoid booking lifecycle ambiguity.
- admin operation marks lesson as no-show; package consequence remains "lesson consumed" (no refund).

10. Slot vs booking consistency rule (`C10`):
- canonical rule:
  - slot is `open` only when there is no active booking (`hold`/`confirmed`) and slot is not blocked.
- align with Epic B active-booking uniqueness strategy to prevent contradictory states.

## 24) Epic D Intake: Billing Packages + Consumption (Received 2026-03-04)

Intake source:
- user-provided `Epic D — Billing: пакеты и списания`, items `D1`-`D12`.

Review status labels:
- `ready` = aligns with current codebase, low migration risk.
- `partial` = base already exists, needs extension/hardening.
- `decision_required` = meaningful conflict/breaking-change risk; resolve first.

### D1. Package statuses `ACTIVE/EXPIRED/DEPLETED`
Status: `decision_required`
- Current `PackageStatusEnum` is `ACTIVE/EXPIRED/CANCELED`.
- `DEPLETED` is not present; `CANCELED` is currently used across schemas/admin KPI counts.
- Requires enum migration and compatibility decision (`replace` vs `add`).

### D2. `GET /admin/packages?student_id&status`
Status: `partial`
- Current package listing is student-scoped (`/billing/packages/students/{student_id}`).
- No global admin list endpoint with status filter yet.

### D3. `POST /admin/packages` (manual create: lessons_total, price, expires_at) + audit
Status: `decision_required`
- Admin package creation already exists (`/billing/packages`) with audit logging.
- Current package model has no `price` field; pricing currently lives in `payments`.
- Requires data-model decision for where package price is stored in manual/no-payment mode.

### D4. Consume lesson on lesson completion (double-charge safe)
Status: `decision_required`
- Current logic consumes lesson on booking confirm (`confirm_booking`), not on completion.
- Switching to completion-based consumption affects:
  - booking flow invariants,
  - cancellation/refund behavior,
  - existing integration/unit tests expecting confirm-time decrement.

### D5. `POST /lessons/{id}/complete` (teacher/admin) triggers consumption
Status: `partial`
- Lessons can already be marked via `PATCH /lessons/{id}` status update.
- No dedicated complete endpoint and no billing side-effect on lesson completion.

### D6. Scheduled package expiration worker/cron
Status: `partial`
- Manual admin endpoint already exists: `POST /billing/packages/expire`.
- No dedicated daily scheduler worker yet; can be wired as cron/system job.

### D7. Confirm without package must fail with clear error
Status: `partial`
- Confirm path already checks `booking.package_id` and raises clear business error if missing.
- Hold flow requires package, so this is mostly defensive path; explicit contract test can be added.

### D8. Idempotent consumption (`complete` called twice)
Status: `decision_required`
- No completion-based consumption currently exists, so idempotency behavior is undefined.
- Depends on D4/D5 accounting model decision.

### D9. Payment provider abstraction v1 (`create_payment`, `handle_webhook`, manual_paid)
Status: `partial`
- Payment CRUD/status flow exists in billing service.
- No provider abstraction layer and no webhook handler contract yet.

### D10. Payments table ready for webhooks (`unique(provider_payment_id)`)
Status: `decision_required`
- Current `payments` table has no `provider_payment_id` column.
- Requires migration + uniqueness constraint + integration contract for provider mapping.

### D11. KPI package sales `GET /admin/kpi/sales?from_utc&to_utc`
Status: `partial`
- Existing admin KPI endpoint exposes aggregate payment/package metrics without time-range filtering.
- Sales KPI endpoint with date range is not implemented.

### D12. Integration test: confirm reserves, complete consumes
Status: `decision_required`
- Current tested behavior is different: confirm already decrements `lessons_left`.
- New test expectation implies accounting model change and coordinated refactor of booking/billing/lessons flows.

Cross-cutting risks to resolve before Epic D implementation:
1. Accounting source of truth must be decided first:
   - consume at `confirm` (current), or
   - reserve at `confirm` + consume at `complete` (requested direction).
2. If switching to reserve/consume model, add explicit reservation state (or counters) to avoid balance drift.
3. Any D4/D12 model change will require synchronized updates to existing integration tests and refund semantics.

## 25) Epic D v1.1 (Auto-Resolved Tasks, 2026-03-04)

Decision scope:
- resolve Epic D conflicts into implementation-ready tasks.

1. Package status migration strategy (`D1`):
- extend package lifecycle to include `DEPLETED` while keeping `CANCELED` as backward-compatible transitional status.
- target status set for v1.1 runtime:
  - `ACTIVE`,
  - `EXPIRED`,
  - `DEPLETED`,
  - `CANCELED` (legacy transitional; deprecate later).
- add migration + mapping rules in docs.

2. Admin package listing (`D2`):
- add `GET /admin/packages` with filters:
  - `student_id`,
  - `status`,
  - pagination.
- keep existing student endpoint unchanged for portal compatibility.

3. Admin manual package creation with price snapshot (`D3`):
- add admin endpoint `POST /admin/packages` as explicit admin contract.
- package payload includes:
  - `student_id`,
  - `lessons_total`,
  - `expires_at`,
  - `price_amount`,
  - `price_currency`.
- store price as package snapshot fields (not only in payments).
- write `audit_logs` action `admin.package.create`.

4. Accounting model shift to reserve/consume (`D4`, `D12`):
- move to two-step lesson accounting:
  - on booking confirm: reserve lesson capacity (no direct consume),
  - on lesson complete: consume lesson (`lessons_left` decrement).
- add reservation state to package model:
  - `lessons_reserved` (integer, default `0`).
- available capacity rule:
  - `available = lessons_left - lessons_reserved`.
- all confirm/hold validation uses available capacity.

5. Lesson completion endpoint (`D5`):
- add `POST /lessons/{id}/complete` (teacher/admin access).
- endpoint sets lesson status to `COMPLETED` and triggers one-time consumption.
- keep `PATCH /lessons/{id}` for generic updates.

6. Idempotent consumption guarantee (`D8`):
- add lesson-level consumption marker:
  - `consumed_at` (nullable UTC timestamp) or equivalent idempotency flag.
- completion flow must be idempotent:
  - repeated `complete` call does not decrement package twice.

7. Cancellation/refund adaptation for reserve model (`D4`, `D7`):
- confirm without package remains hard-fail with explicit business error.
- cancel confirmed booking:
  - `>24h`: release reservation only (`lessons_reserved - 1`),
  - `<=24h`: burn lesson (`lessons_reserved - 1` and `lessons_left - 1`).
- policy logic must call shared helper from Epic C:
  - `can_refund_by_policy(now_utc, slot_start_utc)`.

8. Package expiration scheduling (`D6`):
- keep existing `POST /billing/packages/expire` business logic as expiration core.
- add daily scheduler path (worker or cron) invoking system/admin expiration task.

9. Payment provider abstraction v1 (`D9`):
- introduce provider interface:
  - `create_payment(...)`,
  - `handle_webhook(...)`.
- add `manual_paid` provider implementation for current phase.
- billing service routes provider operations through abstraction, not direct branch logic.

10. Payments webhook readiness (`D10`):
- add payment provider identity fields:
  - `provider_name`,
  - `provider_payment_id`.
- enforce uniqueness with partial unique index:
  - unique `provider_payment_id` when not null.

11. Sales KPI endpoint (`D11`):
- add `GET /admin/kpi/sales?from_utc&to_utc`.
- metric basis:
  - succeeded payments amount,
  - refunded amount,
  - net amount,
  - packages created count and paid conversion counters (where applicable).

12. Integration contract updates (`D12`):
- add integration scenario:
  - confirm booking reserves capacity,
  - lesson complete consumes lesson,
  - verify `lessons_left` and `lessons_reserved` transitions.
- update legacy confirm-decrement assertions to new reserve/consume behavior.

## 26) Epic E v1.1 (Auto-Resolved Tasks, 2026-03-04)

Decision scope:
- convert Epic E into implementation-ready tasks.
- keep already working invariant `booking confirm -> lesson exists (1:1)`; focus on missing capabilities.

1. Lesson creation invariant (`E1`):
- keep current behavior as canonical:
  - lesson is guaranteed on booking confirm,
  - one lesson per booking via unique `lessons.booking_id`.
- no contract migration required; only regression coverage expansion in `E10`.

2. Teacher lessons list endpoint (`E2`):
- add `GET /teacher/lessons?from_utc&to_utc&limit&offset`.
- endpoint is teacher-scoped and returns only teacher-owned lessons.
- implement UTC range filters at repository query level.

3. Teacher report endpoint (`E3`):
- add `POST /teacher/lessons/{id}/report` with payload:
  - `notes`,
  - `homework`,
  - `links` (list of URLs).
- enforce teacher ownership and reuse role guards from lessons domain.

4. Meeting URL support (`E4`):
- add lesson field `meeting_url` (nullable).
- support two assignment modes:
  - manual URL input,
  - template-based generation from admin-configured template.
- store resolved final URL in lesson record.

5. Student lessons endpoint contract (`E5`):
- keep existing `GET /lessons/my` runtime behavior.
- add contract alias `GET /me/lessons` mapped to same service logic for frontend contract stability.

6. Access boundaries (`E6`):
- teacher endpoints (`/teacher/lessons*`) must return only teacher-owned lessons.
- student endpoints (`/me/lessons` and `/lessons/my`) must return only student-owned lessons.
- admin access remains explicit only on admin routes or admin-capable lesson actions.

7. Recording URL v2-ready (`E7`):
- add nullable lesson field `recording_url`.
- expose in lesson read DTO and update/report flows with validation.

8. Minimal link moderation (`E8`):
- add simple content guard for report payload fields (`notes`, `homework`, `links`):
  - reject obvious contact patterns (phone/email/messenger handles/contact keywords),
  - return clear business validation error.
- keep heuristic lightweight and documented as baseline moderation.

9. Report change audit (`E9`):
- write audit log for report updates:
  - action: `lesson.report.update`,
  - include actor id, lesson id, and changed fields metadata (without storing sensitive raw diffs when avoidable).

10. Integration regression for lesson creation (`E10`):
- add integration test:
  - booking confirm creates lesson record,
  - lesson has correct linkage (`booking_id`, `teacher_id`, `student_id`),
  - repeated confirm remains idempotent for lesson creation.

## 27) Epic F v1.1 (Auto-Resolved Tasks, 2026-03-04)

Decision scope:
- implement minimal useful notifications on top of existing outbox/worker baseline.

1. Notification template contract (`F1`):
- introduce template keys:
  - `booking_confirmed`,
  - `booking_canceled`,
  - `lesson_reminder_24h`.
- keep template registry code-based for v1 (no DB template editor yet).
- accept legacy alias `booking_cancelled` as backward-compatible template token during transition.

2. Email delivery stub strategy (`F2`):
- keep delivery mode as stub:
  - worker writes delivery result to application logs,
  - notification records remain persisted in `notifications` table as delivery journal.
- no separate `notification_outbox` table in v1 (reuse existing domain outbox + notifications log).

3. Worker processing baseline (`F3`):
- keep and harden existing `outbox_notifications_worker` loop as primary processor.
- standardize config env vars and error logging for deterministic operations.

4. Trigger mapping (`F4`):
- map booking domain events to templates:
  - `booking.confirmed` -> `booking_confirmed`,
  - `booking.canceled` -> `booking_canceled`,
  - `booking.rescheduled` -> `booking_canceled` + optional new-booking confirmation message.
- centralize event-to-template mapping in notifications worker service.

5. Admin notification log endpoint (`F5`):
- add `GET /admin/notifications` with filters:
  - recipient user id,
  - channel,
  - status,
  - template key,
  - created range.
- endpoint is admin-only and uses paginated output.

6. Reminder 24h worker (`F6`):
- add periodic reminder job (hourly preferred):
  - scans lessons starting in next 24h window,
  - creates `lesson_reminder_24h` notifications.
- add idempotency key (`lesson_id + reminder_type + date`) to prevent duplicate reminders.

7. Test scope note (`F7`):
- generation tests already partially covered in current suite for confirm/cancel outbox emission.
- add focused reminder-generation test only (new behavior), without duplicating existing coverage.

8. Telegram extensibility doc (`F8`):
- add `docs/NOTIFICATIONS_INTEGRATIONS.md` with provider interface contract:
  - `send(message)`,
  - channel-specific payload adapter,
  - retry/error handling expectations.

## 28) Epic G v1.1 (Auto-Resolved Tasks, 2026-03-04)

Decision scope:
- bootstrap `web-admin` frontend in phased mode with backend-contract alignment.

1. App bootstrap (`G1`):
- create `web-admin/` using `Vite + React + TypeScript`.
- include baseline tooling:
  - ESLint,
  - Prettier,
  - env `VITE_API_BASE_URL`.

2. Auth flow contract (`G2`):
- login uses backend identity endpoint:
  - `POST {VITE_API_BASE_URL}/identity/auth/login`.
- v1 token storage:
  - `localStorage` for access/refresh,
  - migration path to httpOnly cookies documented for v2.

3. Protected routing (`G3`):
- enforce token presence and admin role gate for all admin routes.
- on missing/invalid token -> redirect to login.

4. App layout/navigation (`G4`):
- main sections:
  - Teachers,
  - Calendar,
  - Students,
  - Packages,
  - KPI.

5. API client core (`G5`):
- implement typed HTTP client with:
  - auth header injection,
  - refresh-token flow,
  - normalized backend error handling.

6. Teachers pages (`G6`, `G7`):
- list/detail pages integrate with Epic B admin teacher endpoints.
- until Epic B endpoints are live, show deterministic “endpoint unavailable” state instead of silent failure.

7. Calendar features (`G8`, `G9`, `G10`, `G11`, `G12`):
- use FullCalendar week view with teacher filter.
- status legend follows canonical backend status mapping.
- slot create/block/bulk-create modals bind to Epic B endpoints.

8. Bookings flow UI (`G13`, `G14`):
- bookings table + reschedule modal integrate with Epic C admin booking endpoints.

9. Students/packages/KPI pages (`G15`, `G16`, `G17`):
- students/packages pages consume Epic D endpoints.
- KPI page uses existing `/admin/kpi/overview` and future `/admin/kpi/sales`.

10. Build/deploy option (`G18`):
- add optional `web-admin/Dockerfile`.
- add compose profile `admin-ui` with reverse-proxy/static serving integration.

11. UX persistence baseline (`G9`, `H9` dependency):
- persist selected `teacher_id` and common filters in browser storage for fast operator workflow.

## 29) Epic H v1.1 (Auto-Resolved Tasks, 2026-03-04)

Decision scope:
- finalize launch-readiness polish using existing platform baseline.

1. Smoke script expansion (`H1`):
- extend smoke checks to include:
  - login,
  - teacher list retrieval (admin endpoint),
  - slot creation,
  - hold,
  - confirm.
- keep script deterministic and CI-friendly.

2. Runbook documentation refresh (`H2`):
- update `README.md` with:
  - dev setup,
  - migrations,
  - seed,
  - worker runs,
  - web-admin local run.

3. Health/metrics validation (`H3`):
- keep existing `/health` and `/metrics` baseline; add explicit verification step in smoke/ops runbook.

4. Security checklist gate (`H4`):
- verify and document:
  - CORS policy,
  - auth rate limits,
  - response field minimization.
- add automated regression checks where possible.

5. PII exposure constraints (`H5`):
- add API contract tests ensuring role-based field visibility (e.g., no cross-role email leakage).

6. Production config baseline (`H6`):
- consolidate required env/secrets matrix and precedence rules in docs.

7. Backup minimum strategy (`H7`):
- keep existing `pg_dump` scripts as canonical baseline and reference them in release checklist.

8. Load sanity scenario (`H8`):
- add reproducible sanity script/test:
  - generate ~1000 weekly slots,
  - query admin calendar/list endpoint,
  - assert non-failure and acceptable response envelope.

9. Admin UX polish (`H9`):
- ensure quick filters and persisted `teacher_id` selection in web-admin workflow.

10. Release cut (`H10`):
- after passing smoke + sanity + security checks:
  - create new release tag,
  - publish release notes with migration and rollback notes.

## 30) Implementation Order (Corrected, 2026-03-04)

Execution priority for implementation phase:
1. Section `19` (`Backlog v1.1`, Epic A rewritten tasks) — mandatory foundation before domain/UI epics.
2. Section `21` (`Epic B v1.1`) — scheduling/admin calendar core.
3. Section `23` (`Epic C v1.1`) — booking admin flows + policy hardening.
4. Section `25` (`Epic D v1.1`) — billing/accounting model migration.
5. Section `26` (`Epic E v1.1`) — lessons reports/materials.
6. Section `27` (`Epic F v1.1`) — notifications baseline.
7. Section `28` (`Epic G v1.1`) — web-admin UI.
8. Section `29` (`Epic H v1.1`) — launch polish and release.

Gate note:
- `B/C/D` implementation must not start before completing `A` contract/security/RBAC baseline from section `19`.

## 31) Epic A Implementation Progress (Started 2026-03-04)

Implemented in codebase:

1. `A2` unified error envelope:
- `app/shared/exceptions.py` now returns:
  - `{ "error": { "code": "...", "message": "...", "details": ... } }`
  for:
  - domain exceptions,
  - FastAPI HTTP exceptions,
  - request validation errors,
  - unhandled exceptions.

2. `A3` RBAC hardening:
- role dependencies moved to endpoint boundary for core paths:
  - `/admin/**` -> admin only,
  - teacher profile endpoints -> teacher/admin,
  - student hold endpoint -> student only,
  - explicit role guards added for booking/billing/lessons sensitive actions.
- stricter teacher ownership rule enforced in teacher service:
  - only `teacher-owner` or `admin` can create/update teacher profile.

3. `A4` env + CORS:
- added settings:
  - `FRONTEND_ADMIN_ORIGIN`,
  - `JWT_SECRET` (alias with priority over `SECRET_KEY`),
  - existing `DATABASE_URL` remains canonical DB DSN.
- enabled CORS middleware in `app/main.py` with configured origins.

3.1 `A4` env stability hotfix (`DEBUG=release`):
- observed inherited process env collision:
  - parent `codex.exe` process injects `DEBUG=release` into child shells.
- this conflicted with strict boolean parsing for `Settings.debug`.
- mitigation implemented in config parser:
  - `debug=release|prod|production` -> `False`,
  - `debug=debug|dev|development` -> `True`.
- validation coverage added in `tests/test_config_security.py`.

4. `A5` dev seeding baseline:
- `scripts/seed_demo_data.py` rewritten as idempotent target seed:
  - 1 admin,
  - 3 teachers (+ verified teacher profiles),
  - 5 students,
  - 2 active packages,
  - 10 future slots (distributed across demo teachers).

5. `A6` OpenAPI/admin readability:
- added OpenAPI tag descriptions in `app/main.py`.
- added admin schema examples in `app/modules/admin/schemas.py`.

6. `A7` admin audit baseline:
- added audit writes for:
  - admin teacher moderation (`verify/disable` via profile status changes),
  - admin slot creation,
  - admin booking cancel/reschedule.
- audit infrastructure reused from existing `audit_logs`.

7. `A8` UTC normalization:
- schema-level UTC normalization added for incoming datetimes:
  - scheduling slot create,
  - package create,
  - lesson create.

8. `A9` status enum normalization:
- introduced `TeacherStatusEnum` (`pending/verified/disabled`).
- model and schema updated with backward-compatible `is_approved`.
- alembic migration added:
  - `20260304_0002_teacher_status_enum.py`
  with backfill from `is_approved`.

9. `A1` and `A10` docs/contracts:
- added admin contract DTOs:
  - `app/modules/admin/contracts.py` with `*_at_utc` fields.
- added docs:
  - `docs/ADMIN_API.md`,
  - `docs/DOMAIN_RULES.md`.

Verification tasks added/updated:
- tests:
  - `tests/test_error_contract.py`,
  - `tests/test_utc_validation.py`,
  - `tests/test_rbac_access_integration.py`,
  - `tests/test_config_security.py` extended for new settings behavior.

## 32) Epic B Implementation Progress (Started 2026-03-05)

Implemented in codebase:

1. `B1` admin teacher list endpoint with filters:
- added `GET /api/v1/admin/teachers` (admin-only) with filters:
  - `status`,
  - `verified`,
  - `q` (display name + email),
  - `tag`,
  - plus existing pagination (`limit`, `offset`).
- endpoint returns admin list items with:
  - `teacher_id` (uses `users.id`),
  - `profile_id`,
  - `status`,
  - `verified`,
  - `tags`,
  - `created_at_utc`,
  - `updated_at_utc`.

2. Conflict resolution for `B1` (`tag` filter dependency):
- identified conflict: `tag` filtering required relational tags storage that did not exist.
- implemented foundation before endpoint finalization:
  - new table/model `teacher_profile_tags`,
  - profile-tag uniqueness (`teacher_profile_id + tag`),
  - indexes for `teacher_profile_id` and `tag`,
  - SQLAlchemy relationships on `TeacherProfile`.
- alembic migration added:
  - `20260305_0003_teacher_profile_tags.py`.

3. `B2` admin teacher detail endpoint:
- added `GET /api/v1/admin/teachers/{teacher_id}` (admin-only),
  where `teacher_id = users.id` (as fixed in Epic B v1.1 decisions).
- endpoint returns detailed teacher card with:
  - profile fields (`display_name`, `bio`, `experience_years`),
  - moderation fields (`status`, `verified`),
  - account state (`is_active`),
  - tags (`teacher_profile_tags`),
  - UTC timestamps (`created_at_utc`, `updated_at_utc`).
- missing teacher profile returns unified `404` with error envelope.

4. `B3` admin teacher moderation endpoints (`verify` / `disable`) + audit:
- added admin-only endpoints:
  - `POST /api/v1/admin/teachers/{teacher_id}/verify`,
  - `POST /api/v1/admin/teachers/{teacher_id}/disable`.
- moderation behavior aligned with Epic B v1.1 decisions:
  - `verify`: sets `teacher_status=verified` and `is_approved=true`,
  - `disable`: sets `teacher_status=disabled`, `is_approved=false`,
    and `users.is_active=false`.
- both endpoints write immutable entries to `audit_logs` with actions:
  - `admin.teacher.verify`,
  - `admin.teacher.disable`,
  including before/after moderation payload snapshot.

5. `B4` admin slots listing endpoint with UTC filters + aggregated booking status:
- added `GET /api/v1/admin/slots` (admin-only) with filters:
  - `teacher_id`,
  - `from_utc`,
  - `to_utc`,
  - plus pagination (`limit`, `offset`).
- endpoint returns slot rows with:
  - raw slot state (`slot_status`),
  - linked booking snapshot (`booking_id`, `booking_status`),
  - computed `aggregated_booking_status` in canonical admin buckets:
    - `open`,
    - `held`,
    - `confirmed`.
- aggregation rule implemented in admin service:
  - `booked` slot or `confirmed` booking -> `confirmed`,
  - `hold` slot or `hold` booking -> `held`,
  - otherwise -> `open`.
- datetime filters are normalized to UTC and validated:
  - `from_utc <= to_utc` is required.

6. `B5` admin single-slot create endpoint with strict validation:
- added dedicated admin endpoint:
  - `POST /api/v1/admin/slots`,
  with admin contract fields:
  - `teacher_id`,
  - `start_at_utc`,
  - `end_at_utc`.
- integrated strict creation rules in scheduling service:
  - `start_at_utc < end_at_utc`,
  - `start_at_utc` must be in the future,
  - minimum slot duration enforced via config:
    - `SLOT_MIN_DURATION_MINUTES` (default `30`),
  - overlap guard:
    - reject slot creation when interval overlaps any existing slot for the same teacher.
- endpoint returns normalized admin response fields:
  - `slot_id`,
  - `teacher_id`,
  - `created_by_admin_id`,
  - `start_at_utc`,
  - `end_at_utc`,
  - `slot_status`,
  - `created_at_utc`,
  - `updated_at_utc`.

7. `B6` admin slot delete policy with booking safeguard:
- added admin-only endpoint:
  - `DELETE /api/v1/admin/slots/{slot_id}`.
- deletion policy aligned with Epic B v1.1 decision:
  - slot is deleted only when there are no related booking rows,
  - if slot has any booking row, API returns `409` and explicit guidance to use:
    - `POST /api/v1/admin/slots/{slot_id}/block`.
- successful delete writes audit entry:
  - `admin.slot.delete` in `audit_logs`.

8. `B7` admin slot block endpoint with reason + audit:
- introduced explicit slot lifecycle status:
  - `blocked` (added to `SlotStatusEnum`).
- added slot block metadata fields on `availability_slots`:
  - `block_reason`,
  - `blocked_at`,
  - `blocked_by_admin_id`.
- added migration:
  - `20260305_0004_slot_blocking_fields.py`.
- added admin-only endpoint:
  - `POST /api/v1/admin/slots/{slot_id}/block`.
- block behavior:
  - sets `slot_status=blocked`,
  - stores block reason and actor metadata,
  - writes immutable audit entry `admin.slot.block`.
- slot status transitions through scheduling repository now clear block metadata
  when moving out of `blocked` to avoid stale state.

9. `B8` admin bulk slot creation endpoint (base):
- added admin-only endpoint:
  - `POST /api/v1/admin/slots/bulk-create`.
- base bulk-create contract supports:
  - `teacher_id`,
  - `date_from_utc`,
  - `date_to_utc`,
  - `weekdays` (`0..6`),
  - `start_time_utc`,
  - `end_time_utc`,
  - `slot_duration_minutes`.
- service behavior:
  - generates deterministic candidate slots from weekly template,
  - enforces bounded generation via config:
    - `SLOT_BULK_CREATE_MAX_SLOTS` (default `1000`),
  - applies existing strict slot validations per candidate
    (future-time, min duration, overlap),
  - returns deterministic skip list with explicit reason for each skipped candidate.
- bulk operation writes summary audit entry:
  - `admin.slot.bulk_create`.

10. `B9` bulk-create exceptions (`exclude_dates[]`, `exclude_time_ranges[]`):
- extended `POST /api/v1/admin/slots/bulk-create` contract with:
  - `exclude_dates` (list of UTC dates),
  - `exclude_time_ranges` (list of UTC time intervals).
- implemented exclusion precedence in bulk generation:
  - `exclude_dates` has higher priority,
  - then `exclude_time_ranges`,
  - then regular slot validations.
- each excluded candidate is returned in deterministic skip journal with explicit reason:
  - `excluded_date`,
  - `excluded_time_range`.
- bulk audit summary now includes effective exclusion payload for traceability.

11. `B10` service-level anti-overlap in transaction:
- added transactional lock strategy in scheduling repository:
  - `lock_teacher_for_slot_mutation(teacher_id)` uses `SELECT ... FOR UPDATE`
    on teacher row to serialize slot mutations per teacher.
- `create_slot` now acquires lock before overlap check + insert flow,
  keeping overlap validation and creation in one transactional critical section.
- deterministic conflict reporting preserved:
  - overlap failures return business-rule error with conflicting slot metadata
    (`overlap_slot_id`, interval bounds).

12. `B11` DB-level anti-overlap strategy closure:
- Epic B v1.1 approved `locking` as pragmatic DB-level protection for this phase.
- implemented lock-based strategy from B10 is now the active B11 fulfillment:
  - teacher-scope `SELECT ... FOR UPDATE` serialization.
- PostgreSQL exclusion constraint remains intentionally deferred as optional phase-2 hardening
  (no additional schema constraint introduced in this phase).

13. `B12` admin slots stats endpoint with final-bucket semantics:
- added admin-only endpoint:
  - `GET /api/v1/admin/slots/stats?from_utc&to_utc`.
- implemented single-final-bucket counting per slot with approved priority:
  - `completed > canceled > confirmed > held > open`.
- aggregation spans slot + booking + lesson states while preventing double-counting
  by selecting only highest-priority bucket per `slot_id`.
- range filters are UTC-normalized and validated (`from_utc <= to_utc`).

14. `B13` automatic HOLD cleanup worker:
- resolved execution-identity conflict by adding system expiration path in booking service:
  - `BookingService.expire_holds_system()` performs HOLD expiration without user actor,
  - existing admin endpoint flow keeps RBAC and now delegates to this system path.
- stale HOLD expiration logic remains deterministic:
  - set booking status to `expired`,
  - clear `hold_expires_at`,
  - release slot back to `open`,
  - emit outbox event `booking.hold.expired`.
- added dedicated worker executable:
  - `app/workers/booking_holds_expirer.py`,
  with `once/loop` modes via env vars:
  - `BOOKING_HOLDS_EXPIRER_MODE`,
  - `BOOKING_HOLDS_EXPIRER_POLL_SECONDS`,
  - `BOOKING_HOLDS_EXPIRER_LOG_LEVEL`.
- production wiring added:
  - `docker-compose.prod.yml` now runs service `booking-holds-expirer`
    in loop mode by default.
- docs/runtime updates:
  - `README.md` workers and runbook sections updated,
  - `.env.example` includes HOLD-expirer worker variables.

15. `B14` integration test: bulk-create + no-overlap:
- added dedicated HTTP+DB integration scenario:
  - `tests/test_admin_slot_bulk_create_integration.py`.
- scenario flow:
  - register/login `admin` and `teacher`,
  - create seed slot via `POST /api/v1/admin/slots`,
  - call `POST /api/v1/admin/slots/bulk-create` on same teacher/day window
    to force overlap skips on part of generated candidates,
  - validate response includes created slots and deterministic overlap skip reason.
- DB assertion:
  - integration test executes direct PostgreSQL self-join check on `availability_slots`
    for target teacher/day window,
  - verifies overlapping interval pairs count is `0` after bulk-create operation.
- stack behavior:
  - test uses bounded health probe and deterministic skip when local integration stack
    at `http://localhost:8000/health` is unavailable.

Verification tasks added/updated:
- tests:
  - `tests/test_admin_slot_stats.py` (service-level final-bucket aggregation + UTC/range/RBAC),
  - `tests/test_admin_slot_bulk_create.py` (service-level bulk create base flow + limit/exclusions/lock validation),
  - `tests/test_admin_slot_block.py` (service-level slot block flow + 403/404),
  - `tests/test_admin_slot_delete.py` (service-level delete policy: success/403/404/409),
  - `tests/test_admin_slot_create_rules.py` (service-level strict create validation + overlap + lock),
  - `tests/test_admin_teachers_list.py` (service-level behavior + admin role enforcement),
  - `tests/test_admin_teacher_detail.py` (service-level detail behavior + `404`/RBAC),
  - `tests/test_admin_teacher_moderation.py` (service-level verify/disable behavior + `404`/RBAC),
  - `tests/test_admin_slots_list.py` (service-level slot aggregation + UTC/range validation + RBAC),
  - `tests/test_admin_slot_bulk_create_integration.py` (HTTP+DB no-overlap guarantee for bulk-create),
  - `tests/test_booking_rules.py` extended with HOLD expiration admin/system-path checks,
  - `tests/test_booking_holds_expirer_worker.py` (worker run-cycle uses system path + commits tx),
  - `tests/test_rbac_access_integration.py` extended with `/admin/teachers` and
    `/admin/teachers/{teacher_id}` RBAC checks,
  - `tests/test_rbac_access_integration.py` extended with
    `/admin/teachers/{teacher_id}/verify` and `/disable` RBAC checks and audit-log trace check,
  - `tests/test_rbac_access_integration.py` extended with:
    - `/admin/slots` RBAC check,
    - `/admin/slots/stats` RBAC check,
    - `POST /admin/slots` RBAC check,
    - `POST /admin/slots/bulk-create` RBAC check,
    - `DELETE /admin/slots/{slot_id}` RBAC + conflict policy checks,
    - `POST /admin/slots/{slot_id}/block` RBAC + audit trace check.

Latest local checks:
- `py -m poetry run ruff check app/core/config.py app/modules/scheduling app/modules/admin tests/test_admin_slot_bulk_create.py tests/test_rbac_access_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_admin_slot_bulk_create.py tests/test_admin_slot_block.py tests/test_admin_slot_delete.py tests/test_admin_slot_create_rules.py tests/test_admin_slots_list.py tests/test_admin_teacher_moderation.py tests/test_admin_teacher_detail.py tests/test_admin_teachers_list.py tests/test_admin_kpi_overview.py tests/test_admin_operations_overview.py` -> `35 passed`.
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k "admin_teacher_detail_endpoint or admin_teachers_endpoint"` -> `2 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k "admin_teacher_verify_endpoint or admin_teacher_disable_endpoint or admin_teacher_moderation_endpoints_write_audit_logs"` -> `3 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k admin_slots_endpoint_returns_401_403_and_200_by_role` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k "admin_slots_endpoint_returns_401_403_and_200_by_role or admin_create_slot_endpoint_returns_401_403_and_201_by_role"` -> `2 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k "admin_delete_slot_endpoint_returns_401_403_and_204_without_bookings or admin_delete_slot_endpoint_returns_409_when_slot_has_related_booking or admin_block_slot_endpoint_returns_401_403_and_200_and_writes_audit"` -> `3 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k "admin_bulk_create_slots_endpoint_returns_401_403_and_200_by_role or admin_create_slot_endpoint_returns_401_403_and_201_by_role or admin_block_slot_endpoint_returns_401_403_and_200_and_writes_audit"` -> `3 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/modules/admin/schemas.py app/modules/admin/router.py app/modules/scheduling/service.py tests/test_admin_slot_bulk_create.py tests/test_rbac_access_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_admin_slot_bulk_create.py tests/test_admin_slot_block.py tests/test_admin_slot_delete.py tests/test_admin_slot_create_rules.py tests/test_admin_slots_list.py tests/test_admin_teacher_moderation.py tests/test_admin_teacher_detail.py tests/test_admin_teachers_list.py tests/test_admin_kpi_overview.py tests/test_admin_operations_overview.py` -> `37 passed`.
- `py -m poetry run ruff check app/modules/scheduling/repository.py app/modules/scheduling/service.py tests/test_admin_slot_create_rules.py tests/test_admin_slot_bulk_create.py` -> `All checks passed`.
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k admin_bulk_create_slots_endpoint_returns_401_403_and_200_by_role` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/modules/admin/repository.py app/modules/admin/service.py app/modules/admin/router.py app/modules/admin/schemas.py tests/test_admin_slot_stats.py tests/test_rbac_access_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_admin_slot_stats.py tests/test_admin_slot_bulk_create.py tests/test_admin_slot_block.py tests/test_admin_slot_delete.py tests/test_admin_slot_create_rules.py tests/test_admin_slots_list.py tests/test_admin_teacher_moderation.py tests/test_admin_teacher_detail.py tests/test_admin_teachers_list.py tests/test_admin_kpi_overview.py tests/test_admin_operations_overview.py` -> `41 passed`.
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k admin_slot_stats_endpoint_returns_401_403_and_200_by_role` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/modules/booking/service.py app/workers/booking_holds_expirer.py tests/test_booking_rules.py tests/test_booking_holds_expirer_worker.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_booking_rules.py tests/test_booking_holds_expirer_worker.py` -> `11 passed`.
- `py -m poetry run ruff check tests/test_admin_slot_bulk_create_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q -rs tests/test_admin_slot_bulk_create_integration.py` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- full local suite: `py -m poetry run pytest -q` -> `110 passed, 23 skipped`.

## 33) Epic C Implementation Progress (Started 2026-03-05)

Implemented in codebase:

1. `C1` admin booking list endpoint with filters:
- added admin-only endpoint:
  - `GET /api/v1/admin/bookings`.
- filters implemented:
  - `teacher_id`,
  - `student_id`,
  - `status`,
  - `from_utc`,
  - `to_utc`,
  - plus pagination (`limit`, `offset`).
- booking range semantics are repository-level and deterministic:
  - `from_utc`/`to_utc` filter by linked slot start time.
- endpoint returns booking rows with UTC contract fields:
  - booking ids/status/timestamps,
  - package linkage and refund flags,
  - linked slot interval (`slot_start_at_utc`, `slot_end_at_utc`).
- service-level validation:
  - admin-only access,
  - UTC normalization for date-time filters,
  - strict range rule `from_utc <= to_utc`.

2. `C2` admin booking cancel endpoint (reason + admin trace + 24h policy reuse):
- added admin-only endpoint:
  - `POST /api/v1/admin/bookings/{booking_id}/cancel`.
- explicit admin cancel contract now requires non-empty reason:
  - `AdminBookingCancelRequest.reason` (`min_length=1`, `max_length=512`).
- endpoint is implemented as admin wrapper over booking cancel core:
  - delegates to `BookingService.cancel_booking(...)`,
  - preserves existing 24h refund policy behavior from booking domain core.
- conflict resolution applied:
  - existing public cancel payload allows nullable reason (`BookingCancelRequest`),
  - admin flow now enforces required reason via dedicated admin schema without
    breaking student/teacher public API compatibility.
- audit trace hardening for admin cancel:
  - `admin.booking.cancel` payload now includes:
    - `booking_id`,
    - `admin_id`,
    - `reason`,
    - `refund_returned`,
    - `refund_policy_applied` (`refunded` / `no_refund`),
    - final booking status.

3. `C3` admin reschedule endpoint (atomic cancel + new confirmed):
- added admin-only endpoint:
  - `POST /api/v1/admin/bookings/{booking_id}/reschedule`.
- explicit admin reschedule contract:
  - `AdminBookingRescheduleRequest` with required fields:
    - `new_slot_id`,
    - `reason`.
- conflict resolution implemented for student-only HOLD restriction:
  - added internal booking service path `_hold_booking_for_student(...)` that performs
    HOLD validations/creation for a target student without relying on public student-role endpoint.
  - public `hold_booking(...)` keeps existing student-only access and delegates to this core helper.
- `reschedule_booking(...)` now supports admin flow atomically in one request transaction:
  - cancel old booking with explicit reason,
  - hold target slot for same booking student/package,
  - confirm new booking,
  - set `rescheduled_from_booking_id`.
- admin trace hardening for reschedule:
  - outbox `booking.rescheduled` now includes `reason`,
  - audit `admin.booking.reschedule` payload includes:
    - `admin_id`,
    - `old_booking_id`,
    - `new_booking_id`,
    - `old_slot_id`,
    - `new_slot_id`,
    - `reason`.

4. `C4` HOLD concurrency hardening + integration coverage:
- implemented slot-level lock during HOLD creation:
  - `SchedulingRepository.get_slot_by_id_for_update(slot_id)` uses `SELECT ... FOR UPDATE`.
  - booking hold core (`_hold_booking_for_student`) now loads slot via row lock
    before availability checks and status transition to `hold`.
- HOLD expiry semantics remain unchanged:
  - `hold_expires_at = now + BOOKING_HOLD_MINUTES`.
- added integration scenario for concurrent HOLD attempts on same slot:
  - `tests/test_booking_billing_integration.py::test_concurrent_hold_attempts_on_same_slot_allow_only_one_success`.
- scenario verifies:
  - exactly one request succeeds with `200`,
  - competing request fails with business-rule `422` (`Slot is not available`),
  - DB invariant: only one active booking (`hold`/`confirmed`) exists for target slot.

5. `C5`/`C6` confirm consistency and no-past invariant hardening:
- confirm-flow invariants tightened:
  - `confirm_booking(...)` now rejects HOLD confirmation when slot start is in the past
    (`Cannot confirm booking for slot in the past`),
  - package activity/expiration/lessons checks remain in confirm core.
- reschedule no-past behavior hardened:
  - `reschedule_booking(...)` now validates target slot existence and "not in the past"
    before cancellation step,
  - this prevents invalid past-slot reschedule requests from mutating original booking state.
- transaction semantics remain request-transaction scoped via existing session dependency
  (`get_db_session` commit/rollback boundary unchanged).
- coverage:
  - unit tests added for:
    - confirm reject on past slot with unexpired HOLD,
    - admin reschedule reject on past target slot before cancel side-effects.
  - integration scenario added:
    - forced DB setup where slot start already passed while HOLD still unexpired,
    - confirm endpoint returns deterministic business-rule `422`.

6. `C7` unified 24h policy helper + boundary tests:
- extracted reusable refund policy helper:
  - `app/modules/booking/policy.py::can_refund_by_policy(...)`.
- cancel flow now reuses shared helper:
  - `BookingService.cancel_booking(...)` no longer contains inline hour math.
- helper semantics aligned with approved rule:
  - refund is allowed only when `slot_start - now > 24h` (strictly greater).
- boundary coverage added:
  - `23:59:59` -> no refund,
  - `24:00:00` -> no refund,
  - `24:00:01` -> refund.
- coverage includes:
  - policy-unit tests (`tests/test_booking_policy.py`),
  - booking cancel flow boundary tests (`tests/test_booking_rules.py`),
    confirming helper behavior is applied in business flow.

7. `C8` admin audit payload normalization for cancel/reschedule:
- explicit admin audit actions are finalized and normalized:
  - `admin.booking.cancel`,
  - `admin.booking.reschedule`.
- structured payload shape now includes required trace keys:
  - `booking_id`,
  - `old_slot_id`,
  - `new_slot_id`,
  - `reason`,
  - `actor_id`.
- compatibility keys retained:
  - `admin_id` remains present for existing consumers.
- additional admin-cancel metadata preserved:
  - `refund_returned`,
  - `refund_policy_applied`,
  - final booking status.
- reschedule payload keeps linkage fields:
  - `old_booking_id`,
  - `new_booking_id`.

8. `C9` lesson `NO_SHOW` status + admin no-show operation:
- `LessonStatusEnum` extended with terminal status:
  - `no_show`.
- migration added:
  - `alembic/versions/20260305_0005_lesson_no_show_status.py`,
    updates `lesson_status_enum` and includes downgrade mapping
    (`no_show` -> `canceled`).
- added admin-only endpoint:
  - `POST /api/v1/admin/lessons/{lesson_id}/no-show`.
- implemented service-level transition guard in lessons domain:
  - allowed: `scheduled -> no_show`,
  - idempotent: repeated `no_show` keeps state unchanged,
  - rejected: `completed/canceled -> no_show` with deterministic conflict error.
- conflict resolution applied for operational stats:
  - admin slot stats now treat `lesson.no_show` as terminal `completed` bucket
    to avoid stale `confirmed` visibility.
- KPI consistency hardened:
  - admin KPI lesson counters aggregate `no_show` into `lessons_completed`
    so `lessons_total` remains consistent.

9. `C10` consistency hardening for `slot_status` vs `booking_status`:
- resolved active-booking uniqueness conflict on booking schema:
  - added migration `alembic/versions/20260305_0006_active_booking_slot_uniqueness.py`,
  - replaced unconditional `uq_bookings_slot_id` with partial unique index
    `uq_bookings_slot_id_active` scoped to active states (`hold`, `confirmed`).
- ORM alignment:
  - `Booking.slot_id` uniqueness flag removed at model level (kept indexed).
- HOLD flow consistency guard added:
  - `_hold_booking_for_student(...)` now explicitly checks
    `BookingRepository.get_active_booking_for_slot(slot_id)` and rejects
    hold creation when any active booking exists, even if slot row is stale-`open`.
- admin slot projections normalized for re-book lifecycle:
  - `AdminRepository.list_slots(...)` now joins only active bookings,
  - `AdminRepository.list_slot_status_snapshots(...)` now joins only active bookings.
- slot stats bucket consistency updated:
  - terminal booking statuses (`canceled`/`expired`) no longer force `canceled` bucket,
    so `open` slots with only historical terminal bookings are counted as `open`
    unless slot/lesson state is terminal.
- integration contract added:
  - re-booking same slot after cancellation now succeeds and keeps DB invariant:
    only one active booking exists per slot.

Verification tasks added/updated:
- tests:
  - `tests/test_admin_bookings_list.py` (service-level filters, UTC normalization, range validation, RBAC),
  - `tests/test_booking_rules.py` extended with admin cancel audit payload assertions,
  - `tests/test_booking_rules.py` extended with admin reschedule atomic-path and audit assertions,
  - `tests/test_rbac_access_integration.py` extended with
    `/admin/bookings` RBAC check (`401/403/200`),
  - `tests/test_rbac_access_integration.py` extended with
    `/admin/bookings/{booking_id}/cancel` RBAC + successful admin-cancel path.
  - `tests/test_rbac_access_integration.py` extended with
    `/admin/bookings/{booking_id}/reschedule` RBAC + successful admin-reschedule path.
  - `tests/test_booking_billing_integration.py` extended with
    concurrent HOLD integration scenario and DB active-booking assertion.
  - `tests/test_booking_rules.py` extended with confirm/reschedule past-slot invariant checks.
  - `tests/test_booking_billing_integration.py` extended with confirm reject scenario
    for past slot + unexpired HOLD.
  - `tests/test_booking_policy.py` (policy helper 24h boundary coverage).
  - `tests/test_booking_rules.py` extended with cancel refund boundary coverage.
  - `tests/test_booking_rules.py` extended with
    admin cancel/reschedule audit payload key assertions (`actor_id`, slot ids, booking id).
  - `tests/test_lessons_no_show.py` (service-level no-show transition matrix, idempotency, RBAC guard).
  - `tests/test_admin_slot_stats.py` extended with `lesson_status=no_show` terminal bucket mapping.
  - `tests/test_rbac_access_integration.py` extended with
    `/admin/lessons/{lesson_id}/no-show` RBAC + successful admin path.
  - `tests/test_booking_rules.py` extended with C10 hold consistency guards:
    - reject hold when slot has active booking despite stale-`open` slot status,
    - allow re-book hold when only terminal booking exists.
  - `tests/test_booking_billing_integration.py` extended with
    re-book same slot scenario after cancellation (active-booking uniqueness contract).
  - `tests/test_admin_slot_stats.py` updated for C10 bucket mapping where
    `booking_status=expired/canceled` does not force terminal bucket without slot/lesson terminal state.

Latest local checks:
- `py -m poetry run ruff check app/modules/admin/router.py app/modules/admin/schemas.py app/modules/booking/service.py tests/test_booking_rules.py tests/test_rbac_access_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_admin_bookings_list.py` -> `4 passed`.
- `py -m poetry run pytest -q tests/test_booking_rules.py` -> `12 passed`.
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k admin_bookings_endpoint_returns_401_403_and_200_by_role` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k "admin_cancel_booking_endpoint_returns_401_403_and_200_by_role"` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k "admin_cancel_booking_endpoint_returns_401_403_and_200_by_role or admin_reschedule_booking_endpoint_returns_401_403_and_200_by_role"` -> `2 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/modules/scheduling/repository.py app/modules/booking/service.py tests/test_booking_rules.py tests/test_booking_billing_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q -rs tests/test_booking_billing_integration.py -k concurrent_hold_attempts_on_same_slot_allow_only_one_success` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/modules/booking/service.py tests/test_booking_rules.py tests/test_booking_billing_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_booking_rules.py` -> `14 passed`.
- `py -m poetry run pytest -q -rs tests/test_booking_billing_integration.py -k "concurrent_hold_attempts_on_same_slot_allow_only_one_success or confirm_rejects_hold_when_slot_start_already_passed"` -> `2 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/modules/booking/policy.py app/modules/booking/service.py tests/test_booking_policy.py tests/test_booking_rules.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_booking_policy.py tests/test_booking_rules.py` -> `20 passed`.
- `py -m poetry run ruff check app/modules/booking/service.py tests/test_booking_rules.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_booking_rules.py` -> `17 passed`.
- full local suite: `py -m poetry run pytest -q` -> `124 passed, 28 skipped`.
- `py -m poetry run ruff check app/core/enums.py alembic/versions/20260305_0005_lesson_no_show_status.py app/modules/lessons/service.py app/modules/admin/router.py app/modules/admin/service.py app/modules/admin/repository.py tests/test_lessons_no_show.py tests/test_admin_slot_stats.py tests/test_rbac_access_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_lessons_no_show.py tests/test_admin_slot_stats.py` -> `10 passed`.
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k admin_lesson_no_show_endpoint_returns_401_403_and_200_by_role` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/modules/booking/models.py app/modules/booking/repository.py app/modules/booking/service.py app/modules/admin/repository.py app/modules/admin/service.py alembic/versions/20260305_0006_active_booking_slot_uniqueness.py tests/test_booking_rules.py tests/test_booking_billing_integration.py tests/test_admin_slot_stats.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_booking_rules.py tests/test_admin_slot_stats.py` -> `23 passed`.
- `py -m poetry run pytest -q -rs tests/test_booking_billing_integration.py -k "rebook_same_slot_after_cancel_succeeds_with_active_booking_uniqueness or concurrent_hold_attempts_on_same_slot_allow_only_one_success"` -> `2 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run pytest -q tests/test_admin_slots_list.py tests/test_admin_bookings_list.py` -> `8 passed`.

## 34) Epic D Implementation Progress (Started 2026-03-05)

Implemented in codebase:

1. `D1` package status lifecycle extension (`DEPLETED` + compatibility):
- `PackageStatusEnum` extended with new runtime status:
  - `depleted`.
- migration added:
  - `alembic/versions/20260305_0007_package_status_depleted.py`,
    upgrades `package_status_enum` from
    `active/expired/canceled` to `active/expired/depleted/canceled`.
- downgrade compatibility mapping added:
  - `depleted -> canceled` before enum rollback.
- admin KPI read model updated for status expansion:
  - `packages_depleted` counter added to `AdminKpiOverviewRead`,
  - `packages_total` now includes `active + expired + depleted + canceled`.
- conflict resolution for backward compatibility:
  - `canceled` status retained unchanged as legacy transitional status
    per Epic D v1.1 decision.

2. `D2` admin package listing endpoint with filters:
- added admin-only endpoint:
  - `GET /api/v1/admin/packages`.
- filters implemented:
  - `student_id`,
  - `status`,
  - pagination (`limit`, `offset`).
- repository-level deterministic filtering added:
  - `AdminRepository.list_packages(...)` with stable ordering by
    `lesson_packages.created_at DESC`.
- service-level admin gate and DTO serialization added:
  - `AdminService.list_packages(...)`,
  - response DTO: `AdminPackageListItemRead`.
- compatibility preserved:
  - existing student-scoped endpoint `GET /api/v1/billing/packages/students/{student_id}`
    remains unchanged.

3. `D3` admin manual package creation with price snapshot + audit:
- added migration:
  - `alembic/versions/20260305_0008_package_price_snapshot_fields.py`,
    introduces nullable package snapshot fields:
    - `price_amount`,
    - `price_currency`.
- billing package model/repository extended for snapshot persistence:
  - `LessonPackage.price_amount`,
  - `LessonPackage.price_currency`,
  - repository create path supports optional snapshot arguments.
- added explicit admin endpoint:
  - `POST /api/v1/admin/packages`.
- admin create contract implemented with required fields:
  - `student_id`,
  - `lessons_total`,
  - `expires_at_utc`,
  - `price_amount`,
  - `price_currency`.
- billing service added dedicated admin creation path:
  - `BillingService.create_admin_package(...)`.
- required audit action added per Epic D decision:
  - `admin.package.create`.
- compatibility conflict resolved:
  - existing legacy endpoint `POST /api/v1/billing/packages` remains available
    and creates packages without price snapshot (`null` fields) to avoid breaking
    existing portal/integration flows.

4. `D4` reserve/consume accounting shift (phase 1: reserve + availability + cancel adaptation):
- added migration:
  - `alembic/versions/20260306_0009_package_lessons_reserved.py`,
    introduces non-null reservation counter:
    - `lessons_reserved` (default `0`).
- package model/API contract updated with reservation counter:
  - `LessonPackage.lessons_reserved`,
  - package read/list responses include `lessons_reserved`.
- confirm flow switched to reservation semantics:
  - `BookingService.confirm_booking(...)` now reserves capacity
    (`lessons_reserved + 1`) instead of decrementing `lessons_left`.
- hold/confirm validation switched to available-capacity rule:
  - `available = lessons_left - lessons_reserved`,
  - reservation allowed only when `available > 0`.
- cancellation adaptation applied (Epic D `D7` dependency resolved as part of D4):
  - `>24h`: release reservation only (`lessons_reserved - 1`),
  - `<=24h`: burn reserved lesson (`lessons_reserved - 1`, `lessons_left - 1`).
- compatibility conflict resolved:
  - package balance invariants in booking tests/integration contracts updated
    from confirm-time decrement to reservation-time semantics.

5. `D5` lesson completion endpoint with reserve consumption trigger:
- added migration:
  - `alembic/versions/20260306_0010_lesson_consumed_at.py`,
    introduces lesson consumption marker:
    - `lessons.consumed_at` (nullable UTC).
- lessons API contract extended:
  - `POST /api/v1/lessons/{lesson_id}/complete` (teacher/admin only).
- completion business flow implemented in lessons domain:
  - only `scheduled` lesson can transition to `completed`,
  - teacher can complete only own lesson; admin can complete any lesson,
  - completion loads linked booking/package and consumes one reserved lesson
    (`lessons_reserved - 1`, `lessons_left - 1`).
- idempotency hardening included:
  - repeated complete call on already completed lesson does not consume twice,
    controlled by `consumed_at` marker.
- compatibility preserved:
  - existing `PATCH /lessons/{id}` endpoint remains available.

6. `D6` scheduled package expiration worker/cron path:
- system expiration path added in billing domain:
  - `BillingService.expire_packages_system(...)` runs expiration without user-token context.
- existing admin endpoint flow preserved and delegated:
  - `POST /api/v1/billing/packages/expire` keeps admin RBAC and now delegates
    to shared expiration core.
- added dedicated worker executable:
  - `app/workers/packages_expirer.py`.
- worker execution model:
  - `once` mode (single cycle),
  - `loop` mode (polling cycle).
- worker env vars introduced:
  - `PACKAGES_EXPIRER_MODE`,
  - `PACKAGES_EXPIRER_POLL_SECONDS`,
  - `PACKAGES_EXPIRER_LOG_LEVEL`.
- production compose wiring added:
  - `docker-compose.prod.yml` includes service `packages-expirer` in loop mode.
- runtime docs updated:
  - `.env.example` worker vars,
  - `README.md` workers list, worker run commands, operational runbook package-expirer note.

7. `D7` confirm-without-package guard + reserve-model cancellation/refund adaptation:
- reserve-model cancellation adaptation completed in `D4` and now explicitly tracked under `D7`:
  - `>24h`: release reservation only,
  - `<=24h`: burn reserved lesson.
- confirm hard-fail without package preserved and verified:
  - `BookingService.confirm_booking(...)` keeps explicit guard
    `Booking package is required`.
- regression coverage added for explicit confirm-without-package path.

8. `D8` idempotent lesson consumption on repeated `complete`:
- idempotency marker implemented in lessons domain:
  - `lessons.consumed_at`.
- completion logic guarantees one-time package consumption:
  - first `complete` call consumes reserved lesson,
  - repeated `complete` calls return stable completed state without second consume.
- legacy safety path included:
  - if lesson is already `completed` with missing `consumed_at`, service backfills marker
    without extra package charge.

9. `D9` payment provider abstraction v1 (`create_payment`, `handle_webhook`, `manual_paid`):
- provider abstraction layer added in billing domain:
  - `app/modules/billing/providers.py` with contracts:
    - `PaymentProvider` protocol,
    - `PaymentProviderRegistry`,
    - provider results DTOs (`PaymentProviderCreateResult`, `PaymentWebhookResult`).
- `manual_paid` provider implemented as default v1 provider:
  - `create_payment(...)` resolves manual provider intent,
  - `handle_webhook(...)` parses manual webhook payload into normalized internal status update.
- billing service refactored to use provider abstraction instead of direct provider-agnostic branch logic:
  - `BillingService.create_payment(...)` resolves provider via registry and routes create operation,
  - provider result is mapped into payment creation/audit payload,
  - `BillingService.handle_payment_webhook(...)` added for provider webhook routing and status application.
- payment status transition logic unified:
  - shared internal transition helper introduced (`_set_payment_status`) and reused by:
    - admin status update path,
    - webhook status update path.
- compatibility preserved:
  - existing payment API contracts remain valid (legacy clients can omit `provider_name`,
    defaults to `manual_paid`).

10. `D10` payments webhook readiness (`provider_name`, `provider_payment_id`, unique index):
- payments persistence model extended with provider identity fields:
  - `Payment.provider_name` (non-null, default `manual_paid` for new rows),
  - `Payment.provider_payment_id` (nullable).
- migration added:
  - `alembic/versions/20260306_0011_payment_provider_identity_fields.py`:
    - adds both fields,
    - backfills existing rows with `provider_name='manual_paid'`,
    - enforces non-null `provider_name`,
    - adds partial unique index:
      - `uq_payments_provider_payment_id_not_null`
      - unique on `provider_payment_id` when not null.
- billing repository/service contracts updated for provider identity flow:
  - payment create path now persists:
    - `provider_name`,
    - `provider_payment_id`,
  - webhook resolution path can find payment by:
    - `payment_id`,
    - `external_reference`,
    - `provider_payment_id` (new fallback).
- API response contract extended:
  - `PaymentRead` now returns:
    - `provider_name`,
    - `provider_payment_id`.
- compatibility notes:
  - `provider_name` in create request remains optional for legacy clients
    (defaults to `manual_paid`).

11. `D11` sales KPI endpoint (`GET /admin/kpi/sales?from_utc&to_utc`):
- admin API contract added:
  - `GET /api/v1/admin/kpi/sales?from_utc&to_utc`.
- new response schema added:
  - `AdminKpiSalesRead`, includes:
    - payment counters and amounts (`succeeded`, `refunded`, `net`),
    - package creation and paid-conversion counters for range.
- repository aggregation added:
  - `AdminRepository.get_kpi_sales(...)` computes range-scoped metrics for:
    - succeeded/refunded payment counts and sums,
    - net amount,
    - packages created total,
    - packages created with succeeded payment,
    - unpaid packages and conversion ratio.
- service layer added:
  - `AdminService.get_kpi_sales(...)` with:
    - admin-only guard,
    - UTC normalization and range validation (`from_utc <= to_utc`),
    - admin action trace (`admin.kpi.sales.view`).
- docs updated:
  - `README.md` Admin Operations section now documents sales KPI endpoint.

12. `D12` integration contract update (`confirm` reserves, `complete` consumes):
- integration scenario added to booking/billing suite:
  - `tests/test_booking_billing_integration.py::test_confirm_reserves_and_complete_consumes_package_capacity`.
- validated contract in one end-to-end flow:
  - after `hold + confirm`:
    - `lessons_left` unchanged,
    - `lessons_reserved` incremented.
  - after `POST /lessons/{lesson_id}/complete`:
    - lesson transitions to `completed` with `consumed_at`,
    - package transitions to consumption state:
      - `lessons_left` decremented,
      - `lessons_reserved` decremented.
- compatibility note:
  - prior reserve-model integration assertions remain intact; new scenario explicitly
    locks the confirm->complete consumption contract.

Verification tasks added/updated:
- tests:
  - `tests/test_admin_kpi_overview.py` updated with `packages_depleted` snapshot field
    and explicit assertion.
  - `tests/test_admin_packages_list.py` (service-level filtering, serialization, admin RBAC guard).
  - `tests/test_rbac_access_integration.py` extended with
    `/admin/packages` RBAC check (`401/403/200`).
  - `tests/test_billing_payment_rules.py` extended with admin-package-create checks:
    - price snapshot persistence,
    - `admin.package.create` audit action,
    - role/expiration validations.
  - `tests/test_rbac_access_integration.py` extended with
    `POST /admin/packages` RBAC check (`401/403/201`).
  - `tests/test_booking_rules.py` updated for reserve model:
    - confirm reserves capacity,
    - cancel/refund paths release or burn reservation,
    - reschedule invariants preserve expected reservation balance.
  - `tests/test_booking_billing_integration.py` updated for reserve-model expectations:
    - confirm keeps `lessons_left` and increments `lessons_reserved`,
    - cancel/reschedule/re-book assertions adapted to reservation semantics.
  - `tests/test_lessons_complete.py` (service-level completion flow, ownership/RBAC checks,
    booking/package not-found handling, idempotent consumption behavior).
  - `tests/test_rbac_access_integration.py` extended with
    `/lessons/{lesson_id}/complete` RBAC check (`401/403/200`).
  - `tests/test_billing_payment_rules.py` extended with
    `expire_packages_system(...)` coverage (no-actor system path + trigger audit).
  - `tests/test_packages_expirer_worker.py` (worker cycle uses system expiration path + commits tx).
  - `tests/test_booking_rules.py` extended with
    confirm-without-package clear-error assertion (`Booking package is required`).
  - `tests/test_lessons_complete.py` extended with repeated-complete idempotency assertion
    (`consume_calls == 1` across two calls).
  - `tests/test_billing_payment_rules.py` extended with provider-abstraction coverage:
    - payment create path routes via provider registry,
    - webhook path updates payment status through provider result,
    - ignored webhook payload produces no side-effects.
  - `tests/test_billing_payment_rules.py` extended with D10 webhook-readiness checks:
    - provider identity fields persisted on payment create,
    - webhook can resolve payment by `provider_payment_id`.
  - `tests/test_admin_kpi_sales.py` added:
    - sales snapshot mapping,
    - admin action trace,
    - admin-only access and invalid-range guard.
  - `tests/test_rbac_access_integration.py` extended with
    `/admin/kpi/sales` RBAC check (`401/403/200`).
  - `tests/test_booking_billing_integration.py` extended with D12 scenario:
    - confirm reserves,
    - lesson complete consumes reserved lesson.

Latest local checks:
- `py -m poetry run ruff check app/core/enums.py alembic/versions/20260305_0007_package_status_depleted.py app/modules/admin/repository.py app/modules/admin/schemas.py tests/test_admin_kpi_overview.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_admin_kpi_overview.py tests/test_admin_operations_overview.py tests/test_billing_payment_rules.py` -> `17 passed`.
- `py -m poetry run ruff check app/modules/admin/router.py app/modules/admin/service.py app/modules/admin/repository.py app/modules/admin/schemas.py tests/test_admin_packages_list.py tests/test_rbac_access_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_admin_packages_list.py tests/test_admin_bookings_list.py tests/test_admin_kpi_overview.py` -> `9 passed`.
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k admin_packages_endpoint_returns_401_403_and_200_by_role` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/modules/billing/models.py app/modules/billing/repository.py app/modules/billing/schemas.py app/modules/billing/service.py app/modules/admin/router.py app/modules/admin/schemas.py app/modules/admin/repository.py tests/test_billing_payment_rules.py tests/test_admin_packages_list.py tests/test_rbac_access_integration.py alembic/versions/20260305_0008_package_price_snapshot_fields.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_billing_payment_rules.py tests/test_admin_packages_list.py tests/test_admin_kpi_overview.py` -> `21 passed`.
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k "admin_packages_endpoint_returns_401_403_and_200_by_role or admin_create_package_endpoint_returns_401_403_and_201_by_role"` -> `2 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/modules/billing/models.py app/modules/billing/repository.py app/modules/billing/schemas.py app/modules/billing/service.py app/modules/booking/service.py app/modules/admin/schemas.py app/modules/admin/repository.py app/modules/admin/router.py app/modules/admin/contracts.py tests/test_booking_rules.py tests/test_booking_billing_integration.py tests/test_billing_payment_rules.py tests/test_admin_packages_list.py tests/test_rbac_access_integration.py alembic/versions/20260306_0009_package_lessons_reserved.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_booking_rules.py tests/test_billing_payment_rules.py tests/test_admin_packages_list.py tests/test_admin_kpi_overview.py` -> `40 passed`.
- `py -m poetry run pytest -q -rs tests/test_booking_billing_integration.py -k "student_hold_confirm_reserves_package_capacity or cancel_more_than_24h_returns_lesson or cancel_less_than_24h_does_not_return_lesson or rebook_same_slot_after_cancel_succeeds_with_active_booking_uniqueness or reschedule_keeps_balance_and_links_bookings"` -> `5 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/modules/lessons/models.py app/modules/lessons/schemas.py app/modules/lessons/service.py app/modules/lessons/router.py tests/test_lessons_complete.py tests/test_rbac_access_integration.py alembic/versions/20260306_0010_lesson_consumed_at.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_lessons_complete.py tests/test_lessons_no_show.py tests/test_booking_rules.py tests/test_billing_payment_rules.py` -> `47 passed`.
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k "lesson_complete_endpoint_returns_401_403_and_200_by_role or admin_create_package_endpoint_returns_401_403_and_201_by_role"` -> `2 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/modules/billing/service.py app/workers/packages_expirer.py tests/test_packages_expirer_worker.py tests/test_billing_payment_rules.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_billing_payment_rules.py tests/test_packages_expirer_worker.py tests/test_booking_holds_expirer_worker.py` -> `19 passed`.
- `py -m poetry run ruff check tests/test_booking_rules.py app/modules/booking/service.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_booking_rules.py tests/test_billing_payment_rules.py` -> `37 passed`.
- `py -m poetry run ruff check tests/test_lessons_complete.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_lessons_complete.py tests/test_lessons_no_show.py` -> `13 passed`.
- `py -m poetry run ruff check app/modules/billing/providers.py app/modules/billing/service.py app/modules/billing/repository.py app/modules/billing/schemas.py tests/test_billing_payment_rules.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_billing_payment_rules.py` -> `20 passed`.
- `py -m poetry run ruff check app/modules/billing/models.py app/modules/billing/repository.py app/modules/billing/providers.py app/modules/billing/schemas.py app/modules/billing/service.py alembic/versions/20260306_0011_payment_provider_identity_fields.py tests/test_billing_payment_rules.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_billing_payment_rules.py` -> `21 passed`.
- `py -m poetry run ruff check app/modules/admin/router.py app/modules/admin/service.py app/modules/admin/repository.py app/modules/admin/schemas.py tests/test_admin_kpi_sales.py tests/test_rbac_access_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_admin_kpi_sales.py tests/test_admin_kpi_overview.py tests/test_admin_operations_overview.py` -> `7 passed`.
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k admin_sales_kpi_endpoint_returns_401_403_and_200_by_role` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check tests/test_booking_billing_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q -rs tests/test_booking_billing_integration.py -k confirm_reserves_and_complete_consumes_package_capacity` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).

## 35) Epic E Implementation Progress (Started 2026-03-05)

Implemented in codebase:

1. `E2` teacher lessons list endpoint (`GET /teacher/lessons`):
- new teacher-scoped endpoint added:
  - `GET /api/v1/teacher/lessons?from_utc&to_utc&limit&offset`.
- repository-level range filtering added:
  - `LessonsRepository.list_teacher_lessons(...)` with UTC range predicates on
    `lessons.scheduled_start_at`.
- service-level teacher-only guard and range validation added:
  - `LessonsService.list_teacher_lessons(...)`,
  - rejects invalid range (`from_utc > to_utc`) with explicit business error.
- app routing wired:
  - new router `app/modules/lessons/teacher_router.py`,
  - mounted in `app/main.py`.

2. `E3` teacher report endpoint (`POST /teacher/lessons/{id}/report`):
- new teacher-only report endpoint added:
  - `POST /api/v1/teacher/lessons/{lesson_id}/report`.
- report payload contract implemented:
  - `notes`,
  - `homework`,
  - `links` (validated URL list).
- lesson persistence contract extended for report fields:
  - migration added:
    - `alembic/versions/20260306_0012_lesson_report_fields.py`,
      adds nullable `lessons.homework` and `lessons.links`.
  - lesson model/read DTO now includes:
    - `homework`,
    - `links`.
- teacher ownership and role boundaries enforced:
  - only `teacher` role can call endpoint,
  - teacher can update report only for own lesson.
- report update path integrated with lessons service:
  - `LessonsService.report_lesson(...)` uses repository update with normalized links storage.

3. `E4` meeting URL support (manual + template-based generation):
- lesson persistence extended with new nullable field:
  - `lessons.meeting_url`.
- migration added:
  - `alembic/versions/20260306_0013_lesson_meeting_url.py`.
- meeting URL assignment supports two explicit modes in update/report flows:
  - manual mode: pass `meeting_url`,
  - template mode: pass `use_meeting_url_template=true`.
- template source introduced as runtime config:
  - `LESSON_MEETING_URL_TEMPLATE` (`Settings.lesson_meeting_url_template`),
  - supported placeholders:
    - `{lesson_id}`,
    - `{booking_id}`,
    - `{teacher_id}`,
    - `{student_id}`.
- service conflict handling added:
  - rejects mixed mode (`meeting_url` + `use_meeting_url_template=true`),
  - rejects template mode when template is not configured.
- lesson API contract updated:
  - `LessonRead` includes `meeting_url`,
  - `LessonUpdate` and teacher report payload support meeting URL fields.

4. `E5` student lessons endpoint alias (`GET /me/lessons`):
- contract alias added:
  - `GET /api/v1/me/lessons`.
- alias maps to existing lessons listing flow without behavior change:
  - reuses `LessonsService.list_lessons(...)` (same as `/lessons/my`).
- app routing wired:
  - new router `app/modules/lessons/me_router.py`,
  - mounted in `app/main.py`.

5. `E6` access boundaries hardening (teacher/student endpoint isolation):
- student endpoints restricted to student role only:
  - `GET /api/v1/lessons/my`,
  - `GET /api/v1/me/lessons`.
- service-level boundary enforced for student listing path:
  - `LessonsService.list_lessons(...)` now rejects non-student actors with explicit error.
- teacher flows migrated to teacher endpoint contract:
  - teacher lesson lookups in integration test helpers and RBAC scenarios now use
    `GET /api/v1/teacher/lessons`.
- conflict resolved with existing integration harness:
  - updated portal and booking/billing integration test paths to avoid implicit teacher access
    through student aliases.

6. `E7` recording URL v2-ready support:
- lesson persistence extended with nullable field:
  - `lessons.recording_url`.
- migration added:
  - `alembic/versions/20260306_0014_lesson_recording_url.py`.
- lesson API contract extended:
  - `LessonRead` includes `recording_url`.
- update/report flows support recording URL assignment with URL validation:
  - `LessonUpdate.recording_url`,
  - `TeacherLessonReportRequest.recording_url`,
  - lessons service normalizes validated URL into persisted string value.

7. `E8` minimal link/content moderation for lesson report payload:
- baseline moderation helper added:
  - `app/modules/lessons/moderation.py`.
- report payload now rejects obvious direct-contact patterns in:
  - `notes`,
  - `homework`,
  - `links`.
- blocked heuristics include:
  - email-like tokens,
  - phone-like numeric patterns,
  - handle-like tokens (`@...`),
  - known contact/messenger markers in text and links (`t.me`, `wa.me`, `mailto:`, `tel:` etc.).
- clear business validation error returned:
  - `Report contains restricted contact information`.
- moderation scope intentionally limited to teacher report flow as v1 baseline.

8. `E9` report change audit (`lesson.report.update`):
- audit integration added to lessons domain:
  - `LessonsService` now accepts `audit_repository` dependency.
- teacher report flow writes structured audit log for actual changes only:
  - action: `lesson.report.update`,
  - entity: `lesson`,
  - payload includes:
    - `lesson_id`,
    - `changed_fields`,
    - `changed_count`.
- audit payload keeps metadata-only contract:
  - no raw report diffs or sensitive full before/after content snapshots.
- no-op updates do not emit audit entries.

9. `E10` integration regression for lesson creation on confirm:
- integration scenario added:
  - `tests/test_booking_billing_integration.py::test_confirm_creates_single_lesson_and_repeat_confirm_is_idempotent`.
- scenario locks contract:
  - first `confirm` creates lesson linked to booking,
  - repeated `confirm` returns same booking and does not create duplicate lesson.
- linkage assertions included:
  - lesson has expected `booking_id`,
  - lesson has expected `teacher_id`,
  - lesson has expected `student_id`.

10. `E1` lesson creation invariant (`booking confirm -> lesson 1:1`) finalized:
- invariant preserved in booking domain logic:
  - confirm path keeps idempotent helper `_ensure_lesson_for_confirmed_booking(...)`.
- regression coverage expanded via `E10` integration scenario:
  - one lesson per booking under repeated confirm contract.

Verification tasks added/updated:
- tests:
  - `tests/test_teacher_lessons_list.py` added (service-level teacher scope + range validation).
  - `tests/test_rbac_access_integration.py` extended with
    `/teacher/lessons` RBAC check (`401/403/200`).
  - `tests/test_teacher_lesson_report.py` added:
    - teacher ownership checks,
    - report persistence checks for `notes/homework/links`,
    - role/404 guard coverage.
  - `tests/test_rbac_access_integration.py` extended with
    `/teacher/lessons/{lesson_id}/report` RBAC check (`401/403/200`).
  - `tests/test_lesson_meeting_url.py` added:
    - manual `meeting_url` assignment,
    - template-based generation,
    - template-missing guard,
    - mixed manual+template conflict guard.
  - `tests/test_rbac_access_integration.py` extended with
    `/me/lessons` alias RBAC check (`401/403/200`).
  - `tests/test_student_lessons_access.py` added (service-level student-only guard for list path).
  - `tests/test_rbac_access_integration.py` extended with:
    - `/me/lessons` student-only check (`401/403/200`),
    - `/lessons/my` student-only check (`401/403/200`).
  - integration helper/path updates:
    - `tests/test_booking_billing_integration.py` teacher lesson lookup switched to `/teacher/lessons`,
    - `tests/test_portal_auth_flow_integration.py` teacher sequence switched to `/teacher/lessons`.
  - `tests/test_lesson_recording_url.py` added:
    - recording URL update path,
    - recording URL report path,
    - invalid URL validation guards.
  - `tests/test_lesson_report_moderation.py` added:
    - clean payload accepted,
    - reject email in notes,
    - reject phone in homework,
    - reject messenger/contact links.
  - `tests/test_teacher_lesson_report_audit.py` added:
    - audit entry written with changed fields metadata,
    - no audit entry when report payload does not change lesson fields.
  - `tests/test_booking_billing_integration.py` extended with E10 regression:
    - confirm creates one lesson,
    - repeated confirm remains lesson-idempotent with stable linkage fields.

Latest local checks:
- `py -m poetry run ruff check app/main.py app/modules/lessons/repository.py app/modules/lessons/service.py app/modules/lessons/teacher_router.py tests/test_teacher_lessons_list.py tests/test_rbac_access_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_teacher_lessons_list.py tests/test_lessons_complete.py tests/test_lessons_no_show.py` -> `16 passed`.
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k teacher_lessons_endpoint_returns_401_403_and_200_by_role` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/modules/lessons/models.py app/modules/lessons/schemas.py app/modules/lessons/service.py app/modules/lessons/teacher_router.py alembic/versions/20260306_0012_lesson_report_fields.py tests/test_teacher_lesson_report.py tests/test_rbac_access_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_teacher_lesson_report.py tests/test_teacher_lessons_list.py tests/test_lessons_complete.py tests/test_lessons_no_show.py` -> `20 passed`.
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k "teacher_lessons_endpoint_returns_401_403_and_200_by_role or teacher_lesson_report_endpoint_returns_401_403_and_200_by_role"` -> `2 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/core/config.py app/modules/lessons/models.py app/modules/lessons/schemas.py app/modules/lessons/service.py alembic/versions/20260306_0013_lesson_meeting_url.py tests/test_lesson_meeting_url.py tests/test_teacher_lesson_report.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_lesson_meeting_url.py tests/test_teacher_lesson_report.py tests/test_teacher_lessons_list.py tests/test_lessons_complete.py` -> `18 passed`.
- `py -m poetry run ruff check app/main.py app/modules/lessons/me_router.py tests/test_rbac_access_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_teacher_lessons_list.py tests/test_teacher_lesson_report.py tests/test_lesson_meeting_url.py` -> `11 passed`.
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k me_lessons_alias_endpoint_returns_401_403_and_200_by_role` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/modules/lessons/router.py app/modules/lessons/me_router.py app/modules/lessons/service.py tests/test_student_lessons_access.py tests/test_booking_billing_integration.py tests/test_portal_auth_flow_integration.py tests/test_rbac_access_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_student_lessons_access.py tests/test_teacher_lessons_list.py tests/test_teacher_lesson_report.py tests/test_lesson_meeting_url.py` -> `14 passed`.
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k "me_lessons_alias_endpoint_returns_401_403_and_200_by_role or lessons_my_endpoint_returns_401_403_and_200_by_role or teacher_lesson_report_endpoint_returns_401_403_and_200_by_role"` -> `3 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run pytest -q -rs tests/test_portal_auth_flow_integration.py -k portal_teacher_and_admin_sequences_for_role_specific_endpoints` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run ruff check app/modules/lessons/models.py app/modules/lessons/schemas.py app/modules/lessons/service.py alembic/versions/20260306_0014_lesson_recording_url.py tests/test_lesson_recording_url.py tests/test_teacher_lesson_report.py tests/test_lesson_meeting_url.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_lesson_recording_url.py tests/test_lesson_meeting_url.py tests/test_teacher_lesson_report.py tests/test_student_lessons_access.py` -> `14 passed`.
- `py -m poetry run ruff check app/modules/lessons/moderation.py app/modules/lessons/service.py tests/test_lesson_report_moderation.py tests/test_teacher_lesson_report.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_lesson_report_moderation.py tests/test_teacher_lesson_report.py tests/test_lesson_recording_url.py tests/test_lesson_meeting_url.py` -> `15 passed`.
- `py -m poetry run ruff check app/modules/lessons/service.py tests/test_teacher_lesson_report_audit.py tests/test_lesson_report_moderation.py tests/test_teacher_lesson_report.py tests/test_lesson_recording_url.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_teacher_lesson_report_audit.py tests/test_lesson_report_moderation.py tests/test_teacher_lesson_report.py tests/test_lesson_recording_url.py` -> `13 passed`.
- `py -m poetry run ruff check tests/test_booking_billing_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q -rs tests/test_booking_billing_integration.py -k confirm_creates_single_lesson_and_repeat_confirm_is_idempotent` -> `1 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run pytest -q tests/test_booking_rules.py tests/test_student_lessons_access.py tests/test_teacher_lesson_report_audit.py` -> `25 passed`.
- `py -m poetry run ruff check app/main.py app/core/config.py app/modules/lessons/models.py app/modules/lessons/schemas.py app/modules/lessons/service.py app/modules/lessons/router.py app/modules/lessons/me_router.py app/modules/lessons/teacher_router.py app/modules/lessons/moderation.py alembic/versions/20260306_0012_lesson_report_fields.py alembic/versions/20260306_0013_lesson_meeting_url.py alembic/versions/20260306_0014_lesson_recording_url.py tests/test_teacher_lessons_list.py tests/test_teacher_lesson_report.py tests/test_lesson_meeting_url.py tests/test_student_lessons_access.py tests/test_lesson_recording_url.py tests/test_lesson_report_moderation.py tests/test_teacher_lesson_report_audit.py tests/test_booking_billing_integration.py tests/test_portal_auth_flow_integration.py tests/test_rbac_access_integration.py` -> `All checks passed`.
- `py -m poetry run pytest -q tests/test_teacher_lessons_list.py tests/test_teacher_lesson_report.py tests/test_lesson_meeting_url.py tests/test_student_lessons_access.py tests/test_lesson_recording_url.py tests/test_lesson_report_moderation.py tests/test_teacher_lesson_report_audit.py tests/test_lessons_complete.py tests/test_lessons_no_show.py tests/test_booking_rules.py` -> `56 passed`.
- `py -m poetry run pytest -q -rs tests/test_rbac_access_integration.py -k "teacher_lessons_endpoint_returns_401_403_and_200_by_role or me_lessons_alias_endpoint_returns_401_403_and_200_by_role or lessons_my_endpoint_returns_401_403_and_200_by_role or teacher_lesson_report_endpoint_returns_401_403_and_200_by_role"` -> `4 skipped` (integration stack unavailable at `http://localhost:8000/health`).
- `py -m poetry run pytest -q -rs tests/test_booking_billing_integration.py -k "confirm_creates_single_lesson_and_repeat_confirm_is_idempotent or confirm_reserves_and_complete_consumes_package_capacity"` -> `2 skipped` (integration stack unavailable at `http://localhost:8000/health`).

## 36) Epic F Implementation Progress (Started 2026-03-06)

Implemented in codebase:

1. `F1` notification template contract:
- added explicit notification template key contract:
  - `booking_confirmed`,
  - `booking_canceled`,
  - `lesson_reminder_24h`.
- implemented code-based template registry and render helpers:
  - `app/modules/notifications/templates.py`.
- legacy alias support added for transition:
  - `booking_cancelled` normalizes to `booking_canceled`.
- added `NotificationTemplateKeyEnum` to shared enums:
  - `app/core/enums.py`.
- notifications persistence extended with template token journal field:
  - ORM: `Notification.template_key`,
  - migration: `alembic/versions/20260306_0015_notification_template_key.py`.
- notifications API/service contract updated to accept/store canonical template key on manual create flow.

2. `F2` email delivery stub strategy:
- introduced explicit delivery client contract and stub provider:
  - `app/modules/notifications/delivery.py`.
- stub provider behavior:
  - writes delivery attempts to application logs,
  - returns successful send result without external provider dependency.
- outbox worker delivery flow hardened to use delivery client contract:
  - creates notification record first (journal-first),
  - invokes delivery client,
  - marks notification `sent` on success,
  - marks notification `failed` on delivery error/result failure before failing outbox event.
- no new outbox table introduced; existing outbox + `notifications` journal retained.

3. `F3` worker processing baseline hardening:
- worker runtime configuration normalized with new canonical env namespace:
  - `NOTIFICATIONS_OUTBOX_WORKER_*`.
- backward compatibility preserved:
  - legacy `OUTBOX_WORKER_*` env vars still accepted with warning log.
- deterministic env parsing added for:
  - `log_level`,
  - `mode`,
  - `poll_seconds`,
  - `batch_size`,
  - `max_retries`,
  - `base_backoff_seconds`,
  - `max_backoff_seconds`.
- invalid env values now fallback to explicit defaults with warning logs (instead of runtime cast crashes).
- worker startup and per-cycle logging improved:
  - startup config snapshot,
  - cycle success logs with elapsed milliseconds,
  - cycle failure logs with elapsed milliseconds.
- `run_cycle(...)` now accepts resolved config object for stable runtime behavior and testability.

4. `F4` trigger mapping centralized in notifications worker:
- booking-domain trigger mapping moved to explicit template mapping path:
  - `booking.confirmed` -> `booking_confirmed`,
  - `booking.canceled` -> `booking_canceled`,
  - `booking.rescheduled` -> `booking_canceled` + optional `booking_confirmed`.
- reschedule optional confirm behavior implemented with payload flag:
  - `include_new_booking_confirmation` (default `true`).
- booking message rendering now goes through template registry contract:
  - `render_template(...)`,
  - persisted `notifications.template_key` is canonical template token.
- booking event processing remains centralized in `NotificationsOutboxWorker` via dedicated helper methods.

5. `F5` admin notification log endpoint:
- added admin-only paginated endpoint:
  - `GET /api/v1/admin/notifications`.
- filters implemented:
  - `recipient_user_id`,
  - `channel`,
  - `status`,
  - `template_key`,
  - `created_from_utc`,
  - `created_to_utc`.
- repository query path added for notifications journal:
  - `AdminRepository.list_notifications(...)`.
- service-layer validation/normalization added:
  - UTC normalization for created range filters,
  - range validation (`created_from_utc <= created_to_utc`),
  - template-key normalization with legacy alias support (`booking_cancelled` -> `booking_canceled`).
- response contract added:
  - `AdminNotificationListItemRead` (`notification_id`, recipient, channel, template, status, sent/create/update timestamps).

6. `F6` reminder 24h worker:
- added reminder generation worker service:
  - `app/modules/notifications/reminder_worker.py` (`LessonReminder24hWorker`).
- reminder scan behavior implemented:
  - selects `scheduled` lessons starting within next 24 hours (`now .. now+24h`),
  - creates `lesson_reminder_24h` notifications for lesson student recipients.
- periodic executable job added:
  - `app/workers/lesson_reminder_24h_worker.py`,
  - default poll interval `3600s` (hourly).
- idempotency contract implemented using notification-level key:
  - key format: `lesson:{lesson_id}:lesson_reminder_24h:{date}`.
- notifications persistence extended for idempotency:
  - ORM field `Notification.idempotency_key`,
  - migration `alembic/versions/20260306_0016_notification_idempotency_key.py`,
  - unique DB index `uq_notifications_idempotency_key`.
- notifications repository extended:
  - optional `idempotency_key` on create path,
  - `get_by_idempotency_key(...)` helper for duplicate suppression.
- lessons repository extended:
  - `list_scheduled_lessons_starting_between(...)` for reminder candidate scan.

7. `F7` focused reminder-generation test:
- added focused test for new reminder behavior only:
  - `tests/test_lesson_reminder_worker.py::test_reminder_worker_generates_reminder_and_skips_duplicate_by_idempotency_key`.
- test validates:
  - reminder scan window (`now .. now+24h`) invocation,
  - `lesson_reminder_24h` template key assignment,
  - idempotency skip when key already exists,
  - successful `sent` status for newly created reminder notification.

8. `F8` Telegram extensibility documentation:
- added integration guide:
  - `docs/NOTIFICATIONS_INTEGRATIONS.md`.
- documented provider contract:
  - `send(message) -> DeliveryResult`.
- documented channel-adapter approach:
  - transport-specific payload builders per channel (`email`, `telegram`).
- documented retry/error handling expectations:
  - retryable vs non-retryable classification,
  - worker-owned retry path and status transitions.
- documented idempotency/observability expectations for notification delivery providers.

Verification tasks added/updated:
- tests:
  - `tests/test_notification_templates.py` added for:
    - canonical key rendering,
    - legacy alias normalization,
    - unknown-key guard.
  - `tests/test_outbox_notifications_worker.py` updated for repository signature compatibility.
  - `tests/test_outbox_notifications_worker.py` extended for delivery-stub behavior:
    - delivery client invocation on success path,
    - notification journal persistence with `failed` status on delivery failure.
  - `tests/test_outbox_notifications_worker_entrypoint.py` added for:
    - `run_cycle(...)` config wiring + commit behavior,
    - canonical env parsing,
    - legacy env fallback,
    - invalid env default fallback.
  - `tests/test_outbox_notifications_worker.py` extended for booking trigger mapping:
    - template key assertions for `booking.confirmed` and `booking.canceled`,
    - `booking.rescheduled` emits two notifications by default (`canceled` + `confirmed`),
    - `booking.rescheduled` emits only cancel notification when optional confirm is disabled.
  - `tests/test_admin_notifications_list.py` added for:
    - service-level filter pass-through,
    - UTC normalization,
    - created-range validation,
    - legacy template-key alias normalization,
    - unknown template-key rejection,
    - admin-only access guard.
  - `tests/test_rbac_access_integration.py` extended with
    `/admin/notifications` role check (`401/403/200`).
  - `tests/test_lesson_reminder_worker.py` added as focused reminder-generation coverage for Epic F.
  - `docs/NOTIFICATIONS_INTEGRATIONS.md` added as extensibility contract for new delivery channels.

Latest local checks:
- `pytest tests/test_notification_templates.py tests/test_outbox_notifications_worker.py` -> failed (`pytest` command unavailable in shell environment).
- `python -m pytest tests/test_notification_templates.py tests/test_outbox_notifications_worker.py` -> failed (`No module named pytest` in active Python environment).
- `python -m compileall app/core/enums.py app/modules/notifications tests/test_notification_templates.py tests/test_outbox_notifications_worker.py` -> success.
- `python -m compileall app/modules/notifications/delivery.py app/modules/notifications/outbox_worker.py tests/test_outbox_notifications_worker.py` -> success.
- `python -m compileall app/workers/outbox_notifications_worker.py tests/test_outbox_notifications_worker_entrypoint.py` -> success.
- `python -m compileall app/modules/notifications/outbox_worker.py tests/test_outbox_notifications_worker.py` -> success.
- `python -m compileall app/modules/admin/router.py app/modules/admin/service.py app/modules/admin/repository.py app/modules/admin/schemas.py tests/test_admin_notifications_list.py tests/test_rbac_access_integration.py` -> success.
- `python -m compileall app/modules/notifications/models.py app/modules/notifications/repository.py app/modules/notifications/reminder_worker.py app/modules/lessons/repository.py app/workers/lesson_reminder_24h_worker.py alembic/versions/20260306_0016_notification_idempotency_key.py` -> success.
- `python -m compileall tests/test_lesson_reminder_worker.py app/modules/notifications/reminder_worker.py app/workers/lesson_reminder_24h_worker.py` -> success.

## 37) Epic G Implementation Progress (Started 2026-03-06)

Implemented in codebase:

1. `G1` app bootstrap (`web-admin`):
- created new frontend workspace:
  - `web-admin/` using `Vite + React + TypeScript`.
- initial scaffold files added:
  - `web-admin/index.html`,
  - `web-admin/src/main.tsx`,
  - `web-admin/src/App.tsx`,
  - `web-admin/src/styles.css`,
  - TypeScript config trio (`tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`),
  - `web-admin/vite.config.ts`.
- baseline tooling added:
  - ESLint config: `web-admin/eslint.config.mjs`,
  - Prettier config: `web-admin/prettier.config.mjs`.
- environment contract added:
  - `web-admin/.env.example` with `VITE_API_BASE_URL`.
- package/runtime metadata added:
  - `web-admin/package.json`,
  - `web-admin/.gitignore`,
  - `web-admin/README.md`.

2. `G2` auth flow contract:
- implemented login call against backend contract:
  - `POST {VITE_API_BASE_URL}/identity/auth/login`.
- added auth modules:
  - `web-admin/src/features/auth/api.ts`,
  - `web-admin/src/features/auth/types.ts`,
  - `web-admin/src/features/auth/storage.ts`.
- token storage implemented in v1 mode:
  - access/refresh/token_type persisted in `localStorage`,
  - bootstrap load + explicit sign-out clear path wired in app state.
- login UI integrated into `App` with deterministic error surface.
- migration path documented for v2:
  - `web-admin/README.md` now describes planned move to httpOnly cookies.

3. `G3` protected routing:
- app routing migrated to `react-router-dom`:
  - `/login`,
  - `/admin`,
  - fallback redirect.
- admin-route guard implemented:
  - requires token pair presence,
  - validates access token by calling `GET /identity/users/me`,
  - enforces `role.name == "admin"` gate before rendering admin route.
- missing/invalid token behavior:
  - immediate redirect to `/login`,
  - stored token pair is cleared on invalid/forbidden session checks.
- protected-admin state includes deterministic loading state while session validation is in flight.

4. `G4` app layout/navigation:
- added admin shell layout with left navigation and content outlet:
  - `web-admin/src/admin/AdminLayout.tsx`.
- navigation sections implemented as explicit config:
  - `Teachers`,
  - `Calendar`,
  - `Students`,
  - `Packages`,
  - `KPI`.
- added nested admin routes:
  - `/admin/teachers`,
  - `/admin/calendar`,
  - `/admin/students`,
  - `/admin/packages`,
  - `/admin/kpi`,
  - with `/admin` default redirect to `/admin/teachers`.
- section pages scaffolded as deterministic placeholders for upcoming endpoint integrations.
- responsive layout styling added for desktop/mobile behavior in `web-admin/src/styles.css`.

5. `G5` API client core:
- added typed HTTP client:
  - `web-admin/src/shared/api/client.ts`.
- implemented auth header injection using stored token pair.
- implemented refresh-token retry flow:
  - on `401`, client calls `POST /identity/auth/refresh`,
  - stores rotated token pair on success,
  - retries original request exactly once.
- implemented normalized backend error handling:
  - `ApiClientError` with HTTP status + normalized message.
- migrated auth API calls to typed client:
  - login request uses `apiClient.request(..., auth=false)`,
  - current-user request uses authenticated client path.

6. `G6` + `G7` teachers pages (list/detail + deterministic unavailable mode):
- added teacher API integration layer:
  - `web-admin/src/features/teachers/api.ts`,
  - `web-admin/src/features/teachers/types.ts`.
- `Teachers` section now calls:
  - `GET /admin/teachers`,
  - `GET /admin/teachers/{id}`.
- interactive list/detail UI implemented in:
  - `web-admin/src/admin/pages/TeachersPage.tsx`.
- deterministic endpoint-unavailable behavior implemented:
  - when API returns `404/405/501`, page shows explicit “Endpoint unavailable” state with expected endpoint names,
  - avoids silent failures and ambiguous empty states.
- added dedicated layout styles for teacher split-view list/detail in `web-admin/src/styles.css`.

7. `G8` + `G9` + `G10` + `G11` + `G12` calendar features:
- calendar data API client implemented:
  - `web-admin/src/features/slots/api.ts`,
  - `web-admin/src/features/slots/types.ts`.
- FullCalendar week/day view integrated in `Calendar` section:
  - `@fullcalendar/react`,
  - `@fullcalendar/timegrid`,
  - `@fullcalendar/interaction`.
- teacher filter integrated with persisted selection:
  - uses `GET /admin/teachers`,
  - stores selected `teacher_id` in browser storage key `go_admin_calendar_teacher_id`.
- status legend added with canonical slot-status mapping:
  - `open`,
  - `hold`,
  - `booked` (confirmed),
  - `blocked`,
  - `canceled`.
- slot operation modals implemented and bound to endpoints:
  - create slot -> `POST /admin/slots`,
  - block slot -> `POST /admin/slots/{slot_id}/block`,
  - bulk create -> `POST /admin/slots/bulk-create`.
- deterministic endpoint-unavailable mode added for calendar dependencies:
  - explicit unavailable states for missing teachers/slots endpoint group.
- UI styling expanded for calendar toolbar, legend, event actions, and modal forms.
- `web-admin/package.json` updated with FullCalendar dependencies.

8. `G13` + `G14` bookings flow UI:
- added bookings API integration:
  - `web-admin/src/features/bookings/api.ts`,
  - `web-admin/src/features/bookings/types.ts`.
- calendar section extended with bookings table bound to:
  - `GET /admin/bookings` (teacher/range filtered).
- reschedule modal implemented and bound to:
  - `POST /admin/bookings/{id}/reschedule`.
- reschedule UX uses available open slots from current calendar dataset for target slot selection.
- deterministic unavailable mode implemented for booking endpoints in bookings panel.
- table/modals styles extended for bookings operations.

9. `G15` + `G16` + `G17` students/packages/KPI pages:
- package domain API integration added:
  - `web-admin/src/features/packages/api.ts`,
  - `web-admin/src/features/packages/types.ts`.
- KPI API integration added:
  - `web-admin/src/features/kpi/api.ts`,
  - `web-admin/src/features/kpi/types.ts`.
- students page now consumes Epic D package data (`GET /admin/packages`) and renders aggregated student-level package summary.
- packages page now consumes Epic D package list with status filter and tabular package lifecycle view.
- KPI page now consumes:
  - `GET /admin/kpi/overview`,
  - `GET /admin/kpi/sales` with configurable UTC date range.
- deterministic unavailable states added for package/KPI endpoint dependencies.
- dashboard/table/filter styles expanded for students/packages/KPI views.

10. `G18` build/deploy option (`admin-ui`) with reverse-proxy integration:
- added optional admin UI container artifacts:
  - `web-admin/Dockerfile`,
  - `web-admin/nginx.conf`,
  - `web-admin/.dockerignore`.
- production compose now supports optional `admin-ui` profile:
  - service `admin-ui` in `docker-compose.prod.yml`,
  - build args for runtime wiring:
    - `ADMIN_UI_API_BASE_URL` -> `VITE_API_BASE_URL`,
    - `ADMIN_UI_BASE_PATH` -> `VITE_BASE_PATH`.
- reverse-proxy routing extended for admin UI:
  - `ops/nginx/default.conf` routes `/admin/` to `admin-ui`,
  - `/admin` redirects to `/admin/`.
- conflict resolution implemented for static assets behind `/admin/`:
  - `web-admin/vite.config.ts` now supports configurable `VITE_BASE_PATH`,
  - docker profile defaults base path to `/admin/` to keep asset URLs and SPA routing consistent behind proxy.
- env/docs updates:
  - `.env.example` adds `ADMIN_UI_API_BASE_URL` and `ADMIN_UI_BASE_PATH`,
  - `web-admin/.env.example` adds `VITE_BASE_PATH` for local/prod parity,
  - `README.md` documents admin-ui compose profile commands and canonical `/admin/` URL behind proxy.

Verification tasks added/updated:
- static checks:
  - `rg -n ".{101}" web-admin` -> no overlong lines found.
  - `rg -n ".{101}" web-admin/src web-admin/README.md` -> no overlong lines found.
  - `rg -n ".{101}" web-admin/src/App.tsx web-admin/src/main.tsx web-admin/src/features/auth/api.ts web-admin/src/features/auth/types.ts web-admin/src/styles.css` -> no overlong lines found.
  - `rg -n ".{101}" web-admin/src` -> no overlong lines found.
  - `rg -n ".{101}" web-admin/src/shared/api/client.ts web-admin/src/features/auth/api.ts web-admin/src/App.tsx` -> no overlong lines found.
  - `rg -n ".{101}" web-admin/src/admin/pages/TeachersPage.tsx web-admin/src/features/teachers/api.ts web-admin/src/features/teachers/types.ts web-admin/src/styles.css` -> no overlong lines found.
  - `rg -n ".{101}" web-admin/src/admin/pages/CalendarPage.tsx web-admin/src/features/slots/api.ts web-admin/src/features/slots/types.ts web-admin/src/styles.css` -> no overlong lines found.
  - `rg -n ".{101}" web-admin/src/admin/pages/CalendarPage.tsx web-admin/src/features/bookings/api.ts web-admin/src/features/bookings/types.ts web-admin/src/styles.css` -> no overlong lines found.
  - `rg -n ".{101}" web-admin/src/admin/pages/StudentsPage.tsx web-admin/src/admin/pages/PackagesPage.tsx web-admin/src/admin/pages/KpiPage.tsx web-admin/src/features/packages/api.ts web-admin/src/features/packages/types.ts web-admin/src/features/kpi/api.ts web-admin/src/features/kpi/types.ts web-admin/src/styles.css` -> no overlong lines found.
  - `rg -n ".{101}" web-admin/Dockerfile web-admin/nginx.conf web-admin/vite.config.ts web-admin/.env.example docker-compose.prod.yml .env.example ops/nginx/default.conf` -> no overlong lines found.
  - `docker compose -f docker-compose.prod.yml -f docker-compose.proxy.yml --profile admin-ui config -q` -> passed.

Latest local checks:
- Node/npm-based checks (`npm run lint`, `npm run build`) were not executed in this shell session (dependencies not installed yet in `web-admin`).

## 38) Epic H Implementation Progress (Started 2026-03-06)

Implemented in codebase:

1. `H1` smoke script expansion (login + admin teacher list + slot create + hold + confirm):
- expanded deployment smoke flow in:
  - `scripts/deploy_smoke_check.py`.
- smoke script now validates all previously covered health/static/auth probes and additionally runs
  end-to-end operational steps:
  - register + login `admin`, `teacher`, and `student` users,
  - create teacher profile (`POST /api/v1/teachers/profiles`),
  - fetch admin teachers list (`GET /api/v1/admin/teachers`),
  - create admin slot (`POST /api/v1/admin/slots`),
  - create admin package for student (`POST /api/v1/admin/packages`),
  - create student HOLD (`POST /api/v1/booking/hold`),
  - confirm booking (`POST /api/v1/booking/{id}/confirm`).
- deterministic assertions added:
  - admin teachers list must return at least one item,
  - booking confirm result must end in `status=confirmed`.
- script-level helper improvements for maintainability:
  - added `request_json(...)` wrapper for JSON parsing,
  - added `auth_headers(...)` helper for bearer auth reuse.

2. `H2` runbook documentation refresh (`README.md`):
- added consolidated developer runbook section:
  - backend local setup,
  - migrations flow,
  - seed flow,
  - worker run commands,
  - `web-admin` local run.
- updated worker docs to current runtime contract:
  - canonical outbox env var documented:
    - `NOTIFICATIONS_OUTBOX_WORKER_MODE`,
  - legacy alias retained in docs for compatibility:
    - `OUTBOX_WORKER_MODE`.
- added missing reminder worker runbook commands:
  - `python -m app.workers.lesson_reminder_24h_worker` (`once`/`loop`).

3. `H3` health/metrics explicit validation in smoke/ops runbooks:
- release runbook updated:
  - `ops/release_checklist.md` now includes mandatory scripted smoke run command:
    - `docker compose -f docker-compose.prod.yml exec -T app python scripts/deploy_smoke_check.py`.
- added explicit post-smoke probe commands (do-not-skip) for:
  - `/health`,
  - `/ready`,
  - `/metrics` with metrics-family grep validation.
- README deployment runbook synchronized with the same explicit probe verification commands.

4. `H4` security checklist gate (CORS + rate limits + response minimization):
- added automated security-surface regression tests:
  - `tests/test_security_surface.py`.
- regression coverage includes:
  - CORS middleware wiring uses `FRONTEND_ADMIN_ORIGIN` and strict middleware options,
  - identity auth routes keep explicit rate-limit dependencies:
    - register/login/refresh,
  - identity endpoint response models remain minimized and do not expose
    internal/sensitive fields (`password_hash`, `role_id`, `secret_key`).
- security gate documentation updated:
  - `README.md` security controls section now includes explicit regression-gate command,
  - `ops/release_checklist.md` pre-deploy section now requires running that gate.

5. `H5` PII exposure constraints (role-based field visibility tests):
- added dedicated contract-level regression tests:
  - `tests/test_pii_field_visibility.py`.
- automated checks added:
  - non-admin domain DTOs (`teacher/booking/lesson/billing`) do not expose `email`,
  - admin teacher DTOs explicitly retain `email` for admin-only workflows,
  - route-level contract gate:
    - response models containing `email` are allowed only on identity/admin routes.
- security gate docs extended:
  - README security-gate command now includes `tests/test_pii_field_visibility.py`,
  - release checklist pre-deploy security gate command updated to include PII test.

6. `H6` production config baseline docs consolidation:
- added centralized production configuration matrix in `README.md`:
  - runtime `.env` keys matrix (`required` vs `conditional` vs `optional`),
  - CI/CD secrets matrix for deploy and backup-restore workflows,
  - explicit precedence rules (secret-key alias, limiter backend, deploy env source, admin-ui profile scope).
- added release-runbook cross-link:
  - `ops/release_checklist.md` pre-deploy now explicitly requires verification against
    README `Production Config Matrix`.
- conflict-safe documentation strategy used:
  - kept existing deploy section details,
  - added matrix as authoritative consolidated source instead of replacing historical runbook notes.

7. `H7` backup minimum strategy baseline reaffirmed:
- documentation now explicitly declares canonical release backup scripts:
  - `scripts/db_backup.ps1`,
  - `scripts/db_restore.ps1`.
- `README.md` backup section now references release-checklist backup step as canonical execution path.
- `ops/release_checklist.md` section `2) Backup` now starts with the same canonical script baseline.

8. `H8` load sanity scenario (~1000 slots) added:
- added reproducible runtime sanity script:
  - `scripts/load_sanity.py`.
- scenario behavior:
  - registers isolated admin/teacher users,
  - creates teacher profile,
  - bulk-creates weekly slots with target close to `1000` (default `LOAD_SANITY_TARGET_SLOTS=1000`),
  - queries `GET /api/v1/admin/slots` in the generated UTC range,
  - validates non-failure and response envelope consistency (`items`, `total`, target threshold).
- deterministic guardrails:
  - rejects invalid/non-positive target,
  - enforces bulk candidate upper bound (`1000`) before request,
  - fails if bulk create accounting (`created + skipped`) mismatches generated candidates.
- runbook integration:
  - `README.md` deployment section includes load-sanity command and custom target override example,
  - `ops/release_checklist.md` smoke section includes mandatory load-sanity execution and expected pass marker.

9. `H9` admin UX polish (quick filters + persisted teacher selection):
- added shared admin filter storage contract:
  - `web-admin/src/shared/storage/adminFilters.ts`.
- persisted teacher selection now works across admin workflow pages:
  - `CalendarPage` and `TeachersPage` both use shared key
    `go_admin_calendar_teacher_id` via `ADMIN_TEACHER_FILTER_STORAGE_KEY`.
- added quick filters in teachers workflow:
  - `TeachersPage` now supports one-click status filters:
    - `All`,
    - `Verified`,
    - `Pending`,
    - `Disabled`.
- filter persistence:
  - selected teacher status filter is persisted in browser storage key
    `go_admin_teachers_status`.
- teachers API adapter now supports status-filter query wiring:
  - `listTeachers({ status })` maps to `GET /admin/teachers?status=...`.
- UX styling added for quick-filter controls in `web-admin/src/styles.css`.

Verification tasks added/updated:
- static checks:
  - `rg -n ".{101}" scripts/deploy_smoke_check.py` -> no overlong lines found.
  - `python -m compileall scripts/deploy_smoke_check.py` -> success.
  - `rg -n "Development Runbook|Backend local setup|Demo seed data|Workers local run|NOTIFICATIONS_OUTBOX_WORKER_MODE|lesson_reminder_24h_worker|web-admin local run" README.md` -> expected entries found.
  - `rg -n "deploy_smoke_check.py|health/readiness/metrics verification|/metrics" ops/release_checklist.md README.md` -> expected entries found.
  - `python -m compileall tests/test_security_surface.py` -> success.
  - `rg -n ".{101}" tests/test_security_surface.py` -> no overlong lines found.
  - `rg -n "test_security_surface.py|security gate|FRONTEND_ADMIN_ORIGIN|response-model minimization" README.md ops/release_checklist.md` -> expected entries found.
  - `python -m compileall tests/test_pii_field_visibility.py` -> success.
  - `rg -n ".{101}" tests/test_pii_field_visibility.py` -> no overlong lines found.
  - `rg -n "test_pii_field_visibility.py|PII|role-based PII|security regression gate" README.md ops/release_checklist.md` -> expected entries found.
  - `rg -n "Production Config Matrix|Runtime `.env` keys|CI/CD secrets|Precedence Rules|JWT_SECRET overrides|PROD_ENV_FILE_B64" README.md ops/release_checklist.md` -> expected entries found.
  - `rg -n "Canonical minimum backup strategy|scripts/db_backup\\.ps1|scripts/db_restore\\.ps1|2\\) Backup" README.md ops/release_checklist.md` -> expected entries found.
  - `python -m compileall scripts/load_sanity.py` -> success.
  - `rg -n ".{101}" scripts/load_sanity.py` -> no overlong lines found.
  - `rg -n "load_sanity.py|Load sanity passed|LOAD_SANITY_TARGET_SLOTS|~1000" README.md ops/release_checklist.md scripts/load_sanity.py` -> expected entries found.
  - `rg -n ".{101}" web-admin/src/admin/pages/TeachersPage.tsx web-admin/src/admin/pages/CalendarPage.tsx web-admin/src/features/teachers/api.ts web-admin/src/shared/storage/adminFilters.ts web-admin/src/styles.css` -> no overlong lines found.
  - `rg -n "quick-filter|ADMIN_TEACHER_FILTER_STORAGE_KEY|go_admin_calendar_teacher_id|status filter" web-admin/src/admin/pages/TeachersPage.tsx web-admin/src/admin/pages/CalendarPage.tsx web-admin/src/features/teachers/api.ts web-admin/src/shared/storage/adminFilters.ts web-admin/src/styles.css` -> expected entries found.

Latest local checks:
- runtime smoke execution was not performed in this shell session (local integration stack was not started).

