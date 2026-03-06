# Secret Rotation Execution Report

## Window

- Window ID:
  - `SR-2026-03-11-01`
- Planned start:
  - `2026-03-11 04:00 UTC` (`2026-03-11 15:00` Asia/Sakhalin, UTC+11)
- Planned duration:
  - `30 minutes`
- Operator:
  - `<fill>`
- Environment/host:
  - `<fill>`

## Preconditions

- Local dry-run:
  - command: `py -m poetry run python scripts/secret_rotation_dry_run.py --env-file .env --rotation-target auto`
  - result: `<pass/fail>`
  - evidence: `<link or artifact>`
- GitHub dry-run workflow (`.github/workflows/secret-rotation-dry-run.yml`, `confirm=ROTATE`):
  - run URL: `<fill>`
  - result: `<pass/fail>`
- Latest `ci` and `deploy` on `main` before rotation:
  - `ci`: `<run id/status>`
  - `deploy`: `<run id/status>`

## Execution Timeline (UTC)

1. `<timestamp>` backup of target `.env` created
2. `<timestamp>` active signing key rotated (`JWT_SECRET`/`SECRET_KEY`)
3. `<timestamp>` `PROD_ENV_FILE_B64` synced from target host `.env`
4. `<timestamp>` deploy workflow started
5. `<timestamp>` deploy workflow completed

## Rotation Data

- Rotated key target:
  - `<JWT_SECRET | SECRET_KEY>`
- Old key fingerprint (optional/redacted):
  - `<fill>`
- New key fingerprint (optional/redacted):
  - `<fill>`
- GitHub secret sync command used:
  - `powershell -ExecutionPolicy Bypass -File scripts/update_github_secret_prod_env.ps1 -RemoteHost <host> -RemoteUser <user> -RemoteEnvPath /opt/guitaronline/.env`

## Deploy + Smoke Evidence

- Deploy workflow run URL:
  - `<fill>`
- Deploy evidence artifact:
  - `deploy-evidence-<run_id>-<run_attempt>`
- Required markers:
  - `Role-based release gate passed.` -> `<present/missing>`
  - `Smoke checks passed.` -> `<present/missing>`
  - `Smoke markers verified.` -> `<present/missing>`

## Post-Rotation Validation

- Health endpoints:
  - `/health` -> `<status>`
  - `/ready` -> `<status>`
  - `/metrics` -> `<status>`
- Auth flow:
  - register/login/profile with new tokens -> `<pass/fail>`
  - previously issued tokens invalidated -> `<confirmed/not confirmed>`

## Outcome

- Final status:
  - `<success/failure>`
- Rollback executed:
  - `<yes/no>`
- Incident/ticket links:
  - `<fill>`
- Follow-up actions:
  - `<fill>`
