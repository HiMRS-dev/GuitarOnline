# GuitarOnline Context Checkpoint (Updated 2026-02-23)

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
   - workflow added: `.github/workflows/deploy.yml` (`workflow_dispatch`, confirm gate),
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

