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
  printf '[rollback-drill][%s] %s\n' "$(timestamp_utc)" "$*"
}

die() {
  printf '[rollback-drill][%s][error] %s\n' "$(timestamp_utc)" "$*" >&2
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

sanitize_env_value() {
  local value="${1:-}"
  value="${value%$'\r'}"
  if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "${value}"
}

read_env_value() {
  local key="$1"
  local env_file="${DEPLOY_PATH}/.env"
  local raw_value
  raw_value="$(
    awk -v target_key="${key}" '
      $0 ~ "^[[:space:]]*" target_key "[[:space:]]*=" {
        value = $0
        sub(/^[[:space:]]*[^=]+=[[:space:]]*/, "", value)
        sub(/[[:space:]]*$/, "", value)
        print value
        exit
      }
    ' "${env_file}"
  )"
  sanitize_env_value "${raw_value}"
}

resolve_target_sha() {
  local ref_name="$1"
  if git show-ref --verify --quiet "refs/remotes/origin/${ref_name}"; then
    git rev-parse "refs/remotes/origin/${ref_name}"
    return
  fi
  if git show-ref --verify --quiet "refs/tags/${ref_name}"; then
    git rev-parse "refs/tags/${ref_name}"
    return
  fi
  if git rev-parse --verify --quiet "${ref_name}^{commit}" >/dev/null 2>&1; then
    git rev-parse "${ref_name}^{commit}"
    return
  fi
  return 1
}

target_ref="${ROLLBACK_DRILL_TARGET_REF:-main}"
backup_file_input="${ROLLBACK_DRILL_BACKUP_FILE:-}"
report_dir_input="${ROLLBACK_DRILL_REPORT_DIR:-backups/reports/rollback-drill}"
allow_production="${ROLLBACK_DRILL_ALLOW_PRODUCTION:-false}"

require_command docker
require_command git
require_command awk
require_command date
require_command tr
require_command mktemp

if ! docker compose version >/dev/null 2>&1; then
  die "docker compose plugin is not available for user $(id -un)"
fi

if [ ! -d "${DEPLOY_PATH}" ]; then
  die "Deploy path does not exist: ${DEPLOY_PATH}"
fi

cd "${DEPLOY_PATH}"
if [ ! -d ".git" ]; then
  die "Git repository not found in deploy path: ${DEPLOY_PATH}"
fi
if [ ! -f "docker-compose.prod.yml" ]; then
  die "Compose file not found: ${DEPLOY_PATH}/docker-compose.prod.yml"
fi
if [ ! -f "scripts/run_restore_rehearsal_remote.sh" ]; then
  die "Missing restore rehearsal runner script in deploy path."
fi
if [ ! -f "${DEPLOY_PATH}/.env" ]; then
  die "Missing ${DEPLOY_PATH}/.env required for environment guard."
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  die "Rollback drill requires clean git worktree in ${DEPLOY_PATH}"
fi

allow_production="$(printf '%s' "${allow_production}" | tr '[:upper:]' '[:lower:]')"
if [ "${allow_production}" != "true" ] && [ "${allow_production}" != "false" ]; then
  die "ROLLBACK_DRILL_ALLOW_PRODUCTION must be true/false. Got: ${allow_production}"
fi
app_env="$(read_env_value "APP_ENV")"
app_env="$(printf '%s' "${app_env}" | tr '[:upper:]' '[:lower:]')"
if [ -z "${app_env}" ]; then
  app_env="development"
fi
if [ "${allow_production}" != "true" ] && [ "${app_env}" = "production" -o "${app_env}" = "prod" ]; then
  die "Rollback drill is blocked for production APP_ENV unless ROLLBACK_DRILL_ALLOW_PRODUCTION=true."
fi

drill_started_utc="$(timestamp_utc)"
drill_start_ns="$(date -u +%s%N)"

log "Fetching latest repository state"
git fetch origin --tags --prune

original_ref="$(git symbolic-ref -q --short HEAD || true)"
original_sha="$(git rev-parse HEAD)"
target_sha="$(resolve_target_sha "${target_ref}" || true)"
if [ -z "${target_sha}" ]; then
  die "Unable to resolve rollback drill target ref: ${target_ref}"
fi

restore_git_state() {
  if [ -n "${original_ref}" ]; then
    git checkout "${original_ref}" >/dev/null 2>&1 || true
  else
    git checkout --detach "${original_sha}" >/dev/null 2>&1 || true
  fi
}
trap restore_git_state EXIT

checked_out_target="false"
if [ "${target_sha}" != "${original_sha}" ]; then
  log "Simulating deploy checkout to target SHA: ${target_sha}"
  git checkout --detach "${target_sha}" >/dev/null
  checked_out_target="true"
else
  log "Target SHA equals current SHA; checkout simulation is a no-op."
fi

log "Simulating rollback checkout to original SHA: ${original_sha}"
git checkout --detach "${original_sha}" >/dev/null
rollback_sha="$(git rev-parse HEAD)"
if [ "${rollback_sha}" != "${original_sha}" ]; then
  die "Rollback simulation failed: HEAD=${rollback_sha}, expected ${original_sha}"
fi

rehearsal_log="$(mktemp)"
restore_report_dir="${report_dir_input%/}/restore-rehearsal"
log "Running restore rehearsal as part of rollback drill"
if [ -n "${backup_file_input}" ]; then
  DEPLOY_PATH="${DEPLOY_PATH}" \
  RESTORE_REHEARSAL_BACKUP_FILE="${backup_file_input}" \
  RESTORE_REHEARSAL_REPORT_DIR="${restore_report_dir}" \
  bash scripts/run_restore_rehearsal_remote.sh | tee "${rehearsal_log}"
else
  DEPLOY_PATH="${DEPLOY_PATH}" \
  RESTORE_REHEARSAL_REPORT_DIR="${restore_report_dir}" \
  bash scripts/run_restore_rehearsal_remote.sh | tee "${rehearsal_log}"
fi

restore_report_path="$(grep '^restore_rehearsal_report=' "${rehearsal_log}" | tail -n 1 | cut -d '=' -f2-)"
rm -f "${rehearsal_log}"
if [ -z "${restore_report_path}" ]; then
  die "Failed to parse restore rehearsal report path from output."
fi
if [ ! -f "${restore_report_path}" ]; then
  die "Restore rehearsal report file not found: ${restore_report_path}"
fi

restore_status="$(awk -F'"' '/"status"[[:space:]]*:[[:space:]]*"/ {print $4; exit}' "${restore_report_path}")"
if [ "${restore_status}" != "success" ]; then
  die "Restore rehearsal report status is not success: ${restore_status:-<empty>}"
fi

drill_end_ns="$(date -u +%s%N)"
elapsed_ns=$((drill_end_ns - drill_start_ns))
if [ "${elapsed_ns}" -lt 0 ]; then
  elapsed_ns=0
fi
drill_duration_seconds="$(awk -v ns="${elapsed_ns}" 'BEGIN { printf "%.3f", ns / 1000000000 }')"
drill_finished_utc="$(timestamp_utc)"

report_dir="$(resolve_path "${report_dir_input}")"
mkdir -p "${report_dir}"
report_file="${report_dir%/}/rollback-drill-$(date -u +%Y%m%d-%H%M%S).json"
generated_at_utc="$(timestamp_utc)"
restore_report_json="$(tr -d '\r' < "${restore_report_path}")"

if [ -n "${original_ref}" ]; then
  original_ref_json="\"${original_ref}\""
else
  original_ref_json="null"
fi

cat > "${report_file}" <<JSON
{
  "status": "success",
  "generated_at_utc": "${generated_at_utc}",
  "drill_started_at_utc": "${drill_started_utc}",
  "drill_finished_at_utc": "${drill_finished_utc}",
  "drill_duration_seconds": ${drill_duration_seconds},
  "git": {
    "original_ref": ${original_ref_json},
    "original_sha": "${original_sha}",
    "target_ref": "${target_ref}",
    "target_sha": "${target_sha}",
    "checked_out_target": ${checked_out_target},
    "rollback_sha": "${rollback_sha}",
    "rollback_ok": true
  },
  "environment": {
    "app_env": "${app_env}",
    "allow_production": ${allow_production}
  },
  "restore_rehearsal_report_file": "${restore_report_path}",
  "restore_rehearsal": ${restore_report_json}
}
JSON
chmod 600 "${report_file}" || true

log "Rollback drill passed."
echo "  target_ref=${target_ref}"
echo "  original_sha=${original_sha}"
echo "  target_sha=${target_sha}"
echo "  rollback_sha=${rollback_sha}"
echo "  restore_report=${restore_report_path}"
echo "  drill_duration_seconds=${drill_duration_seconds}"
echo "rollback_drill_report=${report_file}"
