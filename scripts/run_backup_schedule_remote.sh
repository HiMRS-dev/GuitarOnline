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
  printf '[backup-schedule][%s] %s\n' "$(timestamp_utc)" "$*"
}

die() {
  printf '[backup-schedule][%s][error] %s\n' "$(timestamp_utc)" "$*" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    die "Required command not found: $1"
  fi
}

validate_positive_integer() {
  local name="$1"
  local value="$2"
  if ! [[ "${value}" =~ ^[0-9]+$ ]]; then
    die "${name} must be a positive integer. Got: ${value}"
  fi
  if [ "${value}" -lt 1 ]; then
    die "${name} must be greater than 0. Got: ${value}"
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

count_backups() {
  local dir="$1"
  local pattern="$2"
  find "${dir}" -maxdepth 1 -type f -name "${pattern}" | wc -l | awk '{print $1}'
}

prune_backups() {
  local dir="$1"
  local pattern="$2"
  local keep="$3"
  local label="$4"
  local pruned=0
  local total=0
  local i=0
  mapfile -t files < <(find "${dir}" -maxdepth 1 -type f -name "${pattern}" -printf '%f\n' | sort -r)
  total="${#files[@]}"
  if [ "${total}" -gt "${keep}" ]; then
    for ((i=keep; i<total; i++)); do
      rm -f "${dir}/${files[${i}]}"
      pruned=$((pruned + 1))
    done
  fi
  log "Retention applied (${label}): total=${total}, keep=${keep}, pruned=${pruned}"
}

compose_file="${COMPOSE_FILE:-docker-compose.prod.yml}"
backup_root="${BACKUP_ROOT:-backups/scheduled}"
daily_keep="${BACKUP_DAILY_KEEP:-7}"
weekly_keep="${BACKUP_WEEKLY_KEEP:-8}"
weekly_day="${BACKUP_WEEKLY_DAY:-1}"
force_weekly="$(normalize_boolean BACKUP_FORCE_WEEKLY "${BACKUP_FORCE_WEEKLY:-false}")"

validate_positive_integer "BACKUP_DAILY_KEEP" "${daily_keep}"
validate_positive_integer "BACKUP_WEEKLY_KEEP" "${weekly_keep}"
if ! [[ "${weekly_day}" =~ ^[1-7]$ ]]; then
  die "BACKUP_WEEKLY_DAY must be in range 1..7 (ISO week day). Got: ${weekly_day}"
fi

require_command docker
require_command find
require_command sort
require_command awk

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

if ! docker compose -f "${compose_file}" exec -T db true >/dev/null 2>&1; then
  die "Database container is not reachable via docker compose exec."
fi

daily_dir="${backup_root%/}/daily"
weekly_dir="${backup_root%/}/weekly"
mkdir -p "${daily_dir}" "${weekly_dir}"

timestamp="$(date -u +%Y%m%d-%H%M%S)"
daily_file="${daily_dir}/guitaronline-daily-${timestamp}.sql"
weekly_file="${weekly_dir}/guitaronline-weekly-${timestamp}.sql"

log "Creating daily backup: ${daily_file}"
docker compose -f "${compose_file}" exec -T db sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
  > "${daily_file}"

if [ ! -s "${daily_file}" ]; then
  die "Backup file is empty: ${daily_file}"
fi
chmod 600 "${daily_file}" || true

dow_utc="$(date -u +%u)"
if [ "${force_weekly}" = "true" ] || [ "${dow_utc}" = "${weekly_day}" ]; then
  cp "${daily_file}" "${weekly_file}"
  chmod 600 "${weekly_file}" || true
  log "Weekly snapshot created: ${weekly_file}"
else
  log "Weekly snapshot skipped (today_utc_day=${dow_utc}, configured_day=${weekly_day})"
fi

prune_backups "${daily_dir}" "guitaronline-daily-*.sql" "${daily_keep}" "daily"
prune_backups "${weekly_dir}" "guitaronline-weekly-*.sql" "${weekly_keep}" "weekly"

daily_count="$(count_backups "${daily_dir}" "guitaronline-daily-*.sql")"
weekly_count="$(count_backups "${weekly_dir}" "guitaronline-weekly-*.sql")"
log "Backup schedule run completed (daily_count=${daily_count}, weekly_count=${weekly_count})."
