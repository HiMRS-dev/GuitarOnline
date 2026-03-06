# GuitarOnline Secret Rotation Schedule

This document tracks approved production key-rotation windows.

## First Approved Apply Window

- Window ID:
  - `SR-2026-03-11-01`
- Status:
  - `scheduled`
- Planned start:
  - `2026-03-11 04:00 UTC` (`2026-03-11 15:00` Asia/Sakhalin, UTC+11)
- Planned duration:
  - `30 minutes`
- Scope:
  - rotate active runtime signing key (`JWT_SECRET` when present, otherwise `SECRET_KEY`),
  - sync GitHub deploy env bundle secret (`PROD_ENV_FILE_B64`),
  - run deploy with role-based smoke gate enabled.

## Preconditions (Must Be Green Before Start)

1. Dry-run is successful on local env:
   - `py -m poetry run python scripts/secret_rotation_dry_run.py --env-file .env --rotation-target auto`
2. GitHub dry-run workflow is successful:
   - `.github/workflows/secret-rotation-dry-run.yml` with `confirm=ROTATE`.
3. Latest `ci` and `deploy` on `main` are green.

## Apply Runbook Reference

- Canonical procedure:
  - `ops/secret_rotation_playbook.md` (section `4) Rotation Procedure (Apply Window)`).
- Execution report template for this window:
  - `ops/secret_rotation_execution_report_2026-03-11.md`.

## Success Criteria

1. Deploy workflow completes with `run_smoke=true`.
2. Smoke output includes:
   - `Role-based release gate passed.`
   - `Smoke checks passed.`
3. Auth flow works with newly issued tokens; old tokens are invalidated.
4. `/health`, `/ready`, `/metrics` return healthy responses.

## Rollback Trigger

Use `ops/secret_rotation_playbook.md` section `5) Rollback` immediately if any success criterion fails.
