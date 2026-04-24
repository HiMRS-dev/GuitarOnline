# ADM-07 Role Parity Report (2026-04-25)

## Scope
- Validate role parity for `admin`, `teacher`, `student`.
- Validate critical chain:
  - `admin schedule update` -> `generated open slots` -> `open slots visibility` for `teacher` and `student`.

## Test Scenario
- Automated integration test:
  - `tests/test_admin_platform_role_parity_integration.py::test_schedule_generation_and_open_slots_parity_by_role`
- Runtime contour:
  - `INTEGRATION_BASE_URL=http://localhost:18000/api/v1`
  - `INTEGRATION_HEALTH_URL=http://localhost:18000/health`
  - smoke-pool reset enabled before test (`reset_test_smoke_pool`).

## Verified Checks
1. RBAC boundary:
   - `GET /admin/teachers/{teacher_id}/schedule`:
     - `teacher` -> `403`,
     - `student` -> `403`,
     - `admin` -> `200`.
2. Schedule chain:
   - `admin` updates schedule via `PUT /admin/teachers/{teacher_id}/schedule`.
   - `admin` sees generated teacher slots via `GET /admin/slots?teacher_id=...`.
   - generated slot IDs are in `open` state.
3. Role parity on open slots:
   - `teacher` sees same generated slot IDs via `GET /scheduling/slots/open?teacher_id=...`.
   - `student` sees same generated slot IDs via `GET /scheduling/slots/open?teacher_id=...`.
4. Teacher-only endpoint guard:
   - `GET /scheduling/teachers/me/schedule`:
     - `teacher` -> `200`,
     - `student` -> `403`.

## Execution Evidence
- Command:
  - `py -m poetry run pytest -q tests/test_admin_platform_role_parity_integration.py`
- Result:
  - `1 passed`.

## Notes
- During first run, probe path was falsely skipped due system proxy interception for `httpx`.
- Integration test fixture now uses `trust_env=False` to avoid proxy contamination and keep local parity checks deterministic.
