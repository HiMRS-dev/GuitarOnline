#!/usr/bin/env bash
set -euo pipefail

if [ -z "${DEPLOY_PATH:-}" ] || [ -z "${REF_NAME:-}" ]; then
  echo "Missing required runtime variables."
  exit 1
fi

timestamp_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log() {
  printf '[deploy][%s] %s\n' "$(timestamp_utc)" "$*"
}

warn() {
  printf '[deploy][%s][warn] %s\n' "$(timestamp_utc)" "$*" >&2
}

die() {
  printf '[deploy][%s][error] %s\n' "$(timestamp_utc)" "$*" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    die "Required command not found: $1"
  fi
}

ensure_repo_checkout() {
  local current_origin
  local path_meta

  mkdir -p "${DEPLOY_PATH}"
  chmod u+rwx "${DEPLOY_PATH}" 2>/dev/null || true

  if command -v stat >/dev/null 2>&1; then
    path_meta="$(stat -c '%U:%G %a' "${DEPLOY_PATH}" 2>/dev/null || true)"
    if [ -n "${path_meta}" ]; then
      log "Deploy path ownership/permissions: ${path_meta}"
    fi
  fi

  if [ ! -w "${DEPLOY_PATH}" ]; then
    die "Deploy path is not writable by user $(id -un): ${DEPLOY_PATH}"
  fi

  if [ ! -d "${DEPLOY_PATH}/.git" ]; then
    if [ -z "${REPO_URL:-}" ]; then
      die "REPO_URL is required to bootstrap an empty target path."
    fi
    log "No git repository detected. Bootstrapping in ${DEPLOY_PATH}"
    git -C "${DEPLOY_PATH}" init
  fi

  if [ -z "${REPO_URL:-}" ]; then
    if ! git -C "${DEPLOY_PATH}" remote get-url origin >/dev/null 2>&1; then
      die "REPO_URL is empty and origin remote is not configured."
    fi
    return
  fi

  if git -C "${DEPLOY_PATH}" remote get-url origin >/dev/null 2>&1; then
    current_origin="$(git -C "${DEPLOY_PATH}" remote get-url origin)"
    if [ "${current_origin}" != "${REPO_URL}" ]; then
      log "Updating origin remote URL"
      git -C "${DEPLOY_PATH}" remote set-url origin "${REPO_URL}"
    fi
  else
    log "Configuring origin remote URL"
    git -C "${DEPLOY_PATH}" remote add origin "${REPO_URL}"
  fi
}

sync_ref() {
  log "Fetching latest repository state"
  git fetch origin --tags --prune

  if git show-ref --verify --quiet "refs/remotes/origin/${REF_NAME}"; then
    log "Checking out branch origin/${REF_NAME}"
    git checkout -B "${REF_NAME}" "origin/${REF_NAME}"
    git pull --ff-only origin "${REF_NAME}"
    return
  fi

  if git show-ref --verify --quiet "refs/tags/${REF_NAME}"; then
    log "Checking out tag ${REF_NAME} in detached mode"
    git checkout --detach "refs/tags/${REF_NAME}"
    return
  fi

  if git rev-parse --verify --quiet "${REF_NAME}^{commit}" >/dev/null 2>&1; then
    log "Checking out commit ${REF_NAME} in detached mode"
    git checkout --detach "${REF_NAME}"
    return
  fi

  die "Unable to resolve deploy ref: ${REF_NAME}"
}

log "=== Stage 1/6: Preflight ==="
require_command git
require_command docker
if ! docker compose version >/dev/null 2>&1; then
  die "docker compose plugin is not available for user $(id -un)"
fi

log "Preparing deploy path ${DEPLOY_PATH}"
ensure_repo_checkout
cd "${DEPLOY_PATH}"
log "Deploy user: $(id -un)"
log "Origin URL: $(git remote get-url origin 2>/dev/null || echo '<unset>')"
log "Requested ref: ${REF_NAME}"
if [ ! -f "${DEPLOY_PATH}/.env" ]; then
  die "Missing ${DEPLOY_PATH}/.env. Ensure PROD_ENV_FILE_B64 is configured and upload step succeeded."
fi
log ".env file detected."

compose_files=(-f docker-compose.prod.yml)
case "${PROFILE:-standard}" in
  standard)
    ;;
  proxy)
    compose_files+=( -f docker-compose.proxy.yml )
    ;;
  *)
    die "Unsupported profile: ${PROFILE}"
    ;;
esac
log "Compose profile selected: ${PROFILE:-standard}"

run_compose() {
  docker compose "${compose_files[@]}" "$@"
}

PREV_SHA=""
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  PREV_SHA="$(git rev-parse HEAD)"
fi
ROLLBACK_DONE="false"
rollback() {
  exit_code=$?
  if [ "${ROLLBACK_DONE}" = "true" ]; then
    exit "${exit_code}"
  fi
  ROLLBACK_DONE="true"

  if [ -n "${PREV_SHA}" ]; then
    warn "Deployment failed. Rolling back to ${PREV_SHA}"
    git checkout "${PREV_SHA}" || true
    run_compose up --build -d || true
    docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head || true
  else
    warn "Deployment failed during initial bootstrap and there is no previous SHA to roll back to."
  fi
  exit "${exit_code}"
}
trap rollback ERR

log "=== Stage 2/6: Git sync ==="
sync_ref
log "Checked out SHA: $(git rev-parse HEAD)"

if [ "${RUN_BACKUP:-true}" = "true" ]; then
  log "=== Stage 3/6: Pre-deploy backup ==="
  log "Creating pre-deploy backup (if db container is running)"
  mkdir -p backups
  ts="$(date +%Y%m%d-%H%M%S)"
  if docker compose -f docker-compose.prod.yml exec -T db true > /dev/null 2>&1; then
    docker compose -f docker-compose.prod.yml exec -T db sh -c \
      'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
      > "backups/predeploy-${ts}.sql"
  else
    warn "Skipping pre-deploy backup: db container is not running yet."
  fi
else
  log "Skipping pre-deploy backup (RUN_BACKUP=${RUN_BACKUP})"
fi

log "=== Stage 4/6: Compose pull/build/up ==="
log "Pulling latest service images where available"
run_compose pull --ignore-pull-failures || true

log "Building and starting services"
run_compose up --build -d

log "=== Stage 5/6: Database migrations ==="
log "Running Alembic migrations"
docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head

if [ "${RUN_SMOKE:-true}" = "true" ]; then
  log "=== Stage 6/6: Smoke checks ==="
  log "Running smoke checks"
  if [ -f scripts/deploy_smoke_check.py ]; then
    docker compose -f docker-compose.prod.yml exec -T app python scripts/deploy_smoke_check.py
  else
    warn "Missing scripts/deploy_smoke_check.py in deployed ref. Running fallback smoke checks."
    docker compose -f docker-compose.prod.yml exec -T app python - <<'PY'
import json
import urllib.error
import urllib.request
from uuid import uuid4

BASE_URL = "http://localhost:8000"


def request(path: str, *, method: str = "GET", body: dict | None = None, headers: dict | None = None, expected: int = 200):
    payload = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=payload, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.getcode()
            content = resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{method} {path} -> {exc.code}: {exc.read().decode('utf-8', errors='ignore')}") from exc
    if status != expected:
        raise RuntimeError(f"{method} {path} -> {status}, expected {expected}")
    return content

for endpoint in [
    "/health",
    "/ready",
    "/docs",
    "/metrics",
    "/portal",
    "/portal/static/app.js",
    "/portal/static/styles.css",
]:
    request(endpoint, expected=200)

suffix = uuid4().hex[:10]
email = f"deploy-smoke-{suffix}@guitaronline.dev"
password = "StrongPass123!"
request(
    "/api/v1/identity/auth/register",
    method="POST",
    body={"email": email, "password": password, "timezone": "UTC", "role": "student"},
    expected=201,
)
login_payload = json.loads(
    request(
        "/api/v1/identity/auth/login",
        method="POST",
        body={"email": email, "password": password},
        expected=200,
    ).decode("utf-8")
)
request(
    "/api/v1/identity/users/me",
    headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    expected=200,
)
print("Smoke checks passed.")
PY
  fi
else
  log "Skipping smoke checks (RUN_SMOKE=${RUN_SMOKE})"
fi

trap - ERR
log "Deployment completed successfully."
log "deployed_sha=$(git rev-parse HEAD)"
