#!/usr/bin/env bash
set -euo pipefail

if [ -z "${DEPLOY_PATH:-}" ]; then
  echo "DEPLOY_PATH is required." >&2
  exit 1
fi

timestamp_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log() {
  printf '[deploy-smoke][%s] %s\n' "$(timestamp_utc)" "$*"
}

die() {
  printf '[deploy-smoke][%s][error] %s\n' "$(timestamp_utc)" "$*" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    die "Required command not found: $1"
  fi
}

normalize_boolean() {
  local name="$1"
  local value="$2"
  case "${value}" in
    true|false)
      printf '%s' "${value}"
      ;;
    *)
      die "${name} must be true or false. Got: ${value}"
      ;;
  esac
}

sync_ref() {
  local ref_name="$1"
  log "Syncing repository to ref ${ref_name}"
  git fetch origin --tags --prune

  if git show-ref --verify --quiet "refs/remotes/origin/${ref_name}"; then
    git checkout -B "${ref_name}" "origin/${ref_name}"
    return
  fi

  if git show-ref --verify --quiet "refs/tags/${ref_name}"; then
    git checkout --detach "refs/tags/${ref_name}"
    return
  fi

  if git rev-parse --verify --quiet "${ref_name}^{commit}" >/dev/null 2>&1; then
    git checkout --detach "${ref_name}"
    return
  fi

  die "Unable to resolve REF_NAME: ${ref_name}"
}

ensure_app_container_reachable() {
  if docker compose -f "${compose_file}" exec -T app true </dev/null >/dev/null 2>&1; then
    return
  fi

  if [ "${auto_start_test_stack}" != "true" ]; then
    die "Test app container is not reachable via docker compose exec."
  fi

  log "Test contour app container is not reachable; starting app service"
  if ! docker compose -f "${compose_file}" up -d --build app; then
    die "Failed to start test contour app service."
  fi

  if ! docker compose -f "${compose_file}" exec -T app true </dev/null >/dev/null 2>&1; then
    die "Test app container is not reachable via docker compose exec after startup."
  fi
}

compose_file="${COMPOSE_FILE:-docker-compose.test.yml}"
auto_start_test_stack="$(normalize_boolean DEPLOY_SMOKE_AUTO_START_TEST_STACK "${DEPLOY_SMOKE_AUTO_START_TEST_STACK:-true}")"
ref_name="${REF_NAME:-main}"

log "Preparing remote deploy smoke check in ${DEPLOY_PATH} (test contour only)"
require_command docker
require_command git
if ! docker compose version >/dev/null 2>&1; then
  die "docker compose plugin is not available for user $(id -un)"
fi

if [ ! -d "${DEPLOY_PATH}" ]; then
  die "Deploy path does not exist: ${DEPLOY_PATH}"
fi

cd "${DEPLOY_PATH}"
if [ ! -d ".git" ]; then
  die "Git repository is not initialized in ${DEPLOY_PATH}"
fi
sync_ref "${ref_name}"

if [ ! -f "${compose_file}" ]; then
  die "Compose file not found: ${compose_file}"
fi
if [ ! -f "scripts/reset_test_smoke_pool.py" ]; then
  die "Smoke-pool reset script not found in repository checkout: scripts/reset_test_smoke_pool.py"
fi
if [ ! -f "scripts/deploy_smoke_check.py" ]; then
  die "Deploy smoke script not found in repository checkout: scripts/deploy_smoke_check.py"
fi

ensure_app_container_reachable

log "Resetting reusable smoke pool in test contour"
if ! docker compose -f "${compose_file}" exec -T app python - < scripts/reset_test_smoke_pool.py; then
  die "Smoke-pool reset command failed."
fi

log "Running deploy smoke check in test contour"
if ! docker compose -f "${compose_file}" exec -T app python - < scripts/deploy_smoke_check.py; then
  die "Deploy smoke check command failed."
fi

log "Remote deploy smoke check finished successfully."
