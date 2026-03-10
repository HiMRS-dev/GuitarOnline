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
  printf '[restore-rehearsal][%s] %s\n' "$(timestamp_utc)" "$*"
}

die() {
  printf '[restore-rehearsal][%s][error] %s\n' "$(timestamp_utc)" "$*" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    die "Required command not found: $1"
  fi
}

resolve_path() {
  local input_path="$1"
  if [[ "${input_path}" = /* ]]; then
    printf '%s' "${input_path}"
    return
  fi
  printf '%s/%s' "${DEPLOY_PATH%/}" "${input_path#./}"
}

compose_file="${COMPOSE_FILE:-docker-compose.prod.yml}"
backup_root="${BACKUP_ROOT:-backups/scheduled}"
backup_dir_input="${RESTORE_REHEARSAL_BACKUP_DIR:-${backup_root%/}/daily}"
backup_file_input="${RESTORE_REHEARSAL_BACKUP_FILE:-}"
legacy_backup_dir_input="${RESTORE_REHEARSAL_LEGACY_BACKUP_DIR:-backups/daily}"
report_dir_input="${RESTORE_REHEARSAL_REPORT_DIR:-backups/reports}"

require_command docker
require_command find
require_command sort
require_command stat
require_command awk
require_command date
require_command tr

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

if [ -n "${backup_file_input}" ]; then
  backup_file="$(resolve_path "${backup_file_input}")"
else
  primary_backup_dir="$(resolve_path "${backup_dir_input}")"
  legacy_backup_dir="$(resolve_path "${legacy_backup_dir_input}")"

  candidate_dirs=("${primary_backup_dir}")
  if [ "${legacy_backup_dir}" != "${primary_backup_dir}" ]; then
    candidate_dirs+=("${legacy_backup_dir}")
  fi

  selected_backup_dir=""
  latest_backup_name=""
  checked_dirs=""
  for candidate_dir in "${candidate_dirs[@]}"; do
    if [ -z "${checked_dirs}" ]; then
      checked_dirs="${candidate_dir}"
    else
      checked_dirs="${checked_dirs}, ${candidate_dir}"
    fi

    if [ ! -d "${candidate_dir}" ]; then
      log "Backup candidate directory does not exist: ${candidate_dir}"
      continue
    fi

    candidate_latest="$(
      find "${candidate_dir}" -maxdepth 1 -type f -name "guitaronline-daily-*.sql" -printf '%f\n' \
        | sort -r \
        | head -n 1
    )"
    if [ -z "${candidate_latest}" ]; then
      log "No daily backup files found in candidate directory: ${candidate_dir}"
      continue
    fi

    selected_backup_dir="${candidate_dir}"
    latest_backup_name="${candidate_latest}"
    break
  done

  if [ -z "${selected_backup_dir}" ] || [ -z "${latest_backup_name}" ]; then
    die "No daily backups found. Checked directories: ${checked_dirs}. Provide RESTORE_REHEARSAL_BACKUP_FILE or RESTORE_REHEARSAL_BACKUP_DIR."
  fi

  backup_file="${selected_backup_dir}/${latest_backup_name}"
fi

if [ ! -s "${backup_file}" ]; then
  die "Backup file is missing or empty: ${backup_file}"
fi

backup_mtime_epoch="$(stat -c %Y "${backup_file}" 2>/dev/null || true)"
if ! [[ "${backup_mtime_epoch}" =~ ^[0-9]+$ ]]; then
  die "Unable to read backup mtime for file: ${backup_file}"
fi
backup_mtime_utc="$(date -u -d "@${backup_mtime_epoch}" +"%Y-%m-%dT%H:%M:%SZ")"

restore_started_utc="$(timestamp_utc)"
restore_started_epoch="$(date -u +%s)"
rpo_seconds=$((restore_started_epoch - backup_mtime_epoch))
if [ "${rpo_seconds}" -lt 0 ]; then
  rpo_seconds=0
fi

verify_db="restore_rehearsal_$(date -u +%Y%m%d_%H%M%S)"
cleanup() {
  docker compose -f "${compose_file}" exec -T db sh -c \
    "psql -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" -d postgres -c \"DROP DATABASE IF EXISTS \\\"${verify_db}\\\";\"" \
    >/dev/null 2>&1 || true
}
trap cleanup EXIT

start_ns="$(date -u +%s%N)"
log "Creating rehearsal database: ${verify_db}"
docker compose -f "${compose_file}" exec -T db sh -c \
  "psql -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" -d postgres -c \"CREATE DATABASE \\\"${verify_db}\\\";\""

log "Restoring backup into rehearsal database"
cat "${backup_file}" | docker compose -f "${compose_file}" exec -T db sh -c \
  "psql -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" -d \"${verify_db}\""

table_count="$(
  docker compose -f "${compose_file}" exec -T db sh -c \
    "psql -t -A -U \"\$POSTGRES_USER\" -d \"${verify_db}\" -c \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';\"" \
    | tr -d '\r\n '
)"
if ! [[ "${table_count}" =~ ^[0-9]+$ ]]; then
  die "Unexpected table count value from verification DB: ${table_count}"
fi
if [ "${table_count}" -le 0 ]; then
  die "Restore rehearsal failed: public schema has no tables in ${verify_db}"
fi

end_ns="$(date -u +%s%N)"
elapsed_ns=$((end_ns - start_ns))
if [ "${elapsed_ns}" -lt 0 ]; then
  elapsed_ns=0
fi
rto_seconds="$(awk -v ns="${elapsed_ns}" 'BEGIN { printf "%.3f", ns / 1000000000 }')"
restore_finished_utc="$(timestamp_utc)"

report_dir="$(resolve_path "${report_dir_input}")"
mkdir -p "${report_dir}"
report_file="${report_dir%/}/restore-rehearsal-$(date -u +%Y%m%d-%H%M%S).json"
generated_at_utc="$(timestamp_utc)"

cat > "${report_file}" <<JSON
{
  "status": "success",
  "generated_at_utc": "${generated_at_utc}",
  "backup_file": "${backup_file}",
  "backup_mtime_utc": "${backup_mtime_utc}",
  "restore_started_at_utc": "${restore_started_utc}",
  "restore_finished_at_utc": "${restore_finished_utc}",
  "verification_db": "${verify_db}",
  "public_table_count": ${table_count},
  "rpo_seconds": ${rpo_seconds},
  "rto_seconds": ${rto_seconds}
}
JSON
chmod 600 "${report_file}" || true

log "Restore rehearsal passed."
echo "  backup_file=${backup_file}"
echo "  verification_db=${verify_db}"
echo "  public_table_count=${table_count}"
echo "  rpo_seconds=${rpo_seconds}"
echo "  rto_seconds=${rto_seconds}"
echo "restore_rehearsal_report=${report_file}"
