# GuitarOnline Secret Rotation Playbook

This runbook formalizes JWT signing-key rotation and synchronization of the deploy env bundle.

## 1) Scope

- Runtime signing key:
  - `JWT_SECRET` (preferred key when present),
  - fallback: `SECRET_KEY` (used only when `JWT_SECRET` is empty).
- Deploy env bundle secret:
  - GitHub repository secret `PROD_ENV_FILE_B64`.

## 2) Risk Controls

1. Key precedence conflict:
   - if `JWT_SECRET` is set, rotating only `SECRET_KEY` has no runtime effect.
2. Session/token impact:
   - rotating signing key invalidates tokens signed with previous key material.
3. Drift conflict:
   - if target-host `.env` is changed but `PROD_ENV_FILE_B64` is not updated, next deploy can revert the key.

## 3) Required Dry-Run (Non-Destructive)

Run dry-run before each planned rotation window.

1. Local dry-run against env file:
   - `py -m poetry run python scripts/secret_rotation_dry_run.py --env-file .env --rotation-target auto`
2. GitHub Actions dry-run against production env bundle:
   - workflow: `.github/workflows/secret-rotation-dry-run.yml`
   - `workflow_dispatch` with `confirm=ROTATE`.
3. Expected report artifacts:
   - `.tmp/security/secret_rotation_dry_run_report.json`,
   - `.tmp/security/secret_rotation_dry_run_report.md`,
   - workflow artifact `secret-rotation-dry-run-report`.

## 4) Rotation Procedure (Apply Window)

1. Backup target-host env:
   - `ssh <user>@<host> "cp /opt/guitaronline/.env /opt/guitaronline/.env.bak-$(date -u +%Y%m%d-%H%M%S)"`
2. Generate replacement signing key:
   - `python -c "import secrets; print(secrets.token_urlsafe(48))"`
3. Update active key in target-host `.env`:
   - rotate `JWT_SECRET` when present,
   - otherwise rotate `SECRET_KEY`.
4. Sync GitHub deploy env bundle:
   - `powershell -ExecutionPolicy Bypass -File scripts/update_github_secret_prod_env.ps1 -RemoteHost <host> -RemoteUser <user> -RemoteEnvPath /opt/guitaronline/.env`
5. Deploy and smoke-check:
   - run `.github/workflows/deploy.yml` with `run_smoke=true`.
6. Verify:
   - `/health`, `/ready`, `/metrics` are healthy,
   - auth flow (register/login/profile) succeeds,
   - old tokens are rejected after rotation.

## 5) Rollback

1. Restore backup env on target host.
2. Re-sync `PROD_ENV_FILE_B64` from restored env file.
3. Redeploy previous known-good ref and rerun smoke checks.

## 6) Scheduled Windows

- Approved production apply windows are tracked in:
  - `ops/secret_rotation_schedule.md`.
