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
alert_on_failure="${SYNTHETIC_OPS_ALERT_ON_FAILURE:-true}"

log "Preparing synthetic ops check in ${DEPLOY_PATH}"
require_command docker
if ! docker compose version >/dev/null 2>&1; then
  die "docker compose plugin is not available for user $(id -un)"
fi

if [ ! -d "${DEPLOY_PATH}" ]; then
  die "Deploy path does not exist: ${DEPLOY_PATH}"
fi

cd "${DEPLOY_PATH}"
if [ ! -f "${compose_file}" ]; then
  die "Compose file not found: ${compose_file}"
fi

no_alert_arg=""
if [ "${alert_on_failure}" != "true" ]; then
  no_alert_arg="--no-alert-on-failure"
fi

log "Running synthetic ops check (base_url=${base_url}, alertmanager=${alertmanager_url})"
docker compose -f "${compose_file}" exec -T app python scripts/synthetic_ops_check.py \
  --base-url "${base_url}" \
  --alertmanager-url "${alertmanager_url}" \
  --alert-duration-minutes "${alert_duration}" \
  --request-timeout-seconds "${request_timeout}" \
  --runbook-url "${runbook_url}" \
  --admin-email "${admin_email}" \
  --teacher-email "${teacher_email}" \
  --student-email "${student_email}" \
  --password "${password}" \
  ${no_alert_arg}

log "Synthetic ops check finished successfully."
