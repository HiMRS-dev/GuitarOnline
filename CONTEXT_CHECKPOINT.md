# GuitarOnline Context Checkpoint (2026-02-19, EOD)

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
  - `tests/test_booking_rules.py` (unit tests for booking/billing rules + idempotency).
  - `tests/test_booking_billing_integration.py` (5 HTTP+DB integration scenarios).

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
- Repo-wide style baseline is not yet enforced:
  - `ruff check app tests` has legacy findings outside recently changed files.
- Docker Hub connectivity is still flaky in this environment:
  - mitigated by `mirror.gcr.io`, but still an external dependency.
- No CI pipeline configured yet (lint/test/migration gates).

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

### Step A: Baseline commit (infra + tests)
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
Status: done locally (pending baseline commit).

### Phase 1: Core domain coherence
Status: completed (2026-02-23).
- Booking <-> Lessons lifecycle integration.
- Outbox event consistency for booking/lesson flows.
- Idempotency guards for critical transitions.

### Phase 2: Billing hardening
Status: in progress (started 2026-02-23).
- Payment status workflows + reconciliation paths. (partially completed)
- Package expiration job/logic and edge-case handling. (partially completed)
- Better audit coverage for financial actions. (partially completed)

### Phase 3: Notifications pipeline
- Outbox consumer/worker for notification dispatch.
- Retries/backoff/dead-letter strategy for failed sends.
- Delivery status observability.

### Phase 4: Admin and operations
- Admin read models for bookings/payments/lessons KPIs.
- Auditable admin actions with traceability.
- Operational endpoints and runbooks.

### Phase 5: Production readiness
- CI (lint + unit + integration + migration checks).
- Security hardening (auth policies, secret handling, rate limits).
- Deployment baseline, monitoring, backup/restore strategy.

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
