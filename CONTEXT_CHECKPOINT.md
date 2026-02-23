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
  - mitigated by `mirror.gcr.io`, but still an external dependency.
- Identity rate limiting now supports shared Redis backend:
  - `AUTH_RATE_LIMIT_BACKEND=redis` uses cross-instance limiter state via Redis,
  - fallback `memory` backend remains process-local and should be used only for dev/single-instance mode,
  - for production with `memory`, explicit acknowledgement remains required:
    `AUTH_RATE_LIMIT_ALLOW_IN_MEMORY_IN_PRODUCTION=true`,
  - `X-Forwarded-For` is trusted only from configured proxies (`AUTH_RATE_LIMIT_TRUSTED_PROXY_IPS`).
- Monitoring stack remains lightweight:
  - observability is currently API/read-model based (no external metrics backend configured).

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
  - covered by `tests/test_health_readiness.py`.
  - added backup/restore scripts for dockerized PostgreSQL:
    - `scripts/db_backup.ps1`,
    - `scripts/db_restore.ps1`.
  - updated `README.md` with:
    - liveness/readiness probe usage,
    - backup/restore operational commands.
  - added deployment baseline compose profile: `docker-compose.prod.yml`:
    - `db`,
    - `app`,
    - `outbox-worker`.
  - updated `README.md` with production compose bring-up and migration command.
  - latest local suite status: `48 passed`.
- Repo-wide style baseline completed:
  - `ruff check app tests` is now green locally.
  - CI lint job switched from scoped files to full `app/tests` check.
- Structural hardening follow-up completed:
  - production secret guard now rejects placeholder patterns `change-me*` (not only exact `change-me`).
  - production startup now requires explicit acknowledgement of process-local limiter:
    - `AUTH_RATE_LIMIT_ALLOW_IN_MEMORY_IN_PRODUCTION=true`.
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
