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
  printf '[synthetic-ops][%s] %s\n' "$(timestamp_utc)" "$*"
}

die() {
  printf '[synthetic-ops][%s][error] %s\n' "$(timestamp_utc)" "$*" >&2
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

resolve_alert_on_failure() {
  local contour_value="$1"
  local value="$2"
  case "${value}" in
    auto)
      if [ "${contour_value}" = "test" ]; then
        printf 'false'
      else
        printf 'true'
      fi
      ;;
    true|false)
      printf '%s' "${value}"
      ;;
    *)
      die "SYNTHETIC_OPS_ALERT_ON_FAILURE must be auto, true or false. Got: ${value}"
      ;;
  esac
}

normalize_contour() {
  local value="$1"
  case "${value}" in
    live|test)
      printf '%s' "${value}"
      ;;
    *)
      die "SYNTHETIC_OPS_CONTOUR must be live or test. Got: ${value}"
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

  if [ "${contour}" != "test" ] || [ "${auto_start_test_stack}" != "true" ]; then
    die "App container is not reachable via docker compose exec."
  fi

  log "Test contour app container is not reachable; starting app service"
  if ! docker compose -f "${compose_file}" up -d --build app; then
    die "Failed to start test contour app service."
  fi

  if ! docker compose -f "${compose_file}" exec -T app true </dev/null >/dev/null 2>&1; then
    die "App container is not reachable via docker compose exec after test contour startup."
  fi
}

contour="$(normalize_contour "${SYNTHETIC_OPS_CONTOUR:-live}")"
compose_file="${COMPOSE_FILE:-docker-compose.prod.yml}"
base_url="${SYNTHETIC_OPS_BASE_URL:-http://localhost:8000}"
alertmanager_url="${SYNTHETIC_OPS_ALERTMANAGER_URL:-http://alertmanager:9093}"
alert_duration="${SYNTHETIC_OPS_ALERT_DURATION_MINUTES:-30}"
request_timeout="${SYNTHETIC_OPS_REQUEST_TIMEOUT_SECONDS:-30}"
runbook_url="${SYNTHETIC_OPS_RUNBOOK_URL:-ops/release_checklist.md}"
admin_email="${SYNTHETIC_OPS_ADMIN_EMAIL:-synthetic-ops-admin@guitaronline.dev}"
teacher_email="${SYNTHETIC_OPS_TEACHER_EMAIL:-synthetic-ops-teacher@guitaronline.dev}"
student_email="${SYNTHETIC_OPS_STUDENT_EMAIL:-synthetic-ops-student@guitaronline.dev}"
password="${SYNTHETIC_OPS_PASSWORD:-StrongPass123!}"
alert_on_failure="$(resolve_alert_on_failure "${contour}" "${SYNTHETIC_OPS_ALERT_ON_FAILURE:-auto}")"
auto_start_test_stack="$(normalize_boolean SYNTHETIC_OPS_AUTO_START_TEST_STACK "${SYNTHETIC_OPS_AUTO_START_TEST_STACK:-false}")"
ref_name="${REF_NAME:-main}"

if [ "${contour}" = "test" ]; then
  compose_file="${COMPOSE_FILE:-docker-compose.test.yml}"
  admin_email="${SYNTHETIC_OPS_ADMIN_EMAIL:-smoke-admin-1@guitaronline.dev}"
  teacher_email="${SYNTHETIC_OPS_TEACHER_EMAIL:-smoke-teacher-1@guitaronline.dev}"
  student_email="${SYNTHETIC_OPS_STUDENT_EMAIL:-smoke-student-1@guitaronline.dev}"
  password="${SYNTHETIC_OPS_PASSWORD:-StrongPass123!}"
  auto_start_test_stack="$(normalize_boolean SYNTHETIC_OPS_AUTO_START_TEST_STACK "${SYNTHETIC_OPS_AUTO_START_TEST_STACK:-true}")"
fi

log "Preparing synthetic ops check in ${DEPLOY_PATH} (contour=${contour})"
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
if [ ! -f "scripts/synthetic_ops_check.py" ]; then
  die "Synthetic check script not found in repository checkout: scripts/synthetic_ops_check.py"
fi
if [ "${contour}" = "test" ] && [ ! -f "scripts/reset_test_smoke_pool.py" ]; then
  die "Smoke-pool reset script not found in repository checkout: scripts/reset_test_smoke_pool.py"
fi
ensure_app_container_reachable

if [ "${contour}" = "test" ]; then
  log "Resetting reusable smoke pool in test contour"
  if ! docker compose -f "${compose_file}" exec -T app python - < scripts/reset_test_smoke_pool.py; then
    die "Smoke-pool reset command failed."
  fi
fi

synthetic_cmd=(
  docker compose -f "${compose_file}" exec -T app python -
  --base-url "${base_url}"
  --alertmanager-url "${alertmanager_url}"
  --alert-duration-minutes "${alert_duration}"
  --request-timeout-seconds "${request_timeout}"
  --runbook-url "${runbook_url}"
  --admin-email "${admin_email}"
  --teacher-email "${teacher_email}"
  --student-email "${student_email}"
  --password "${password}"
)
if [ "${alert_on_failure}" != "true" ]; then
  synthetic_cmd+=(--no-alert-on-failure)
fi

log "Running synthetic ops check (ref=${ref_name}, base_url=${base_url}, alertmanager=${alertmanager_url}, alert_on_failure=${alert_on_failure})"
if ! "${synthetic_cmd[@]}" < scripts/synthetic_ops_check.py; then
  die "Synthetic ops check command failed."
fi

log "Synthetic ops check finished successfully."
