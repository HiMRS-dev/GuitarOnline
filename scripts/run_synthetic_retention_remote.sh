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
  printf '[synthetic-retention][%s] %s\n' "$(timestamp_utc)" "$*"
}

die() {
  printf '[synthetic-retention][%s][error] %s\n' "$(timestamp_utc)" "$*" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    die "Required command not found: $1"
  fi
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

compose_file="${COMPOSE_FILE:-docker-compose.prod.yml}"
retention_days="${SYNTHETIC_RETENTION_DAYS:-14}"
email_prefixes="${SYNTHETIC_RETENTION_EMAIL_PREFIXES:-synthetic-ops-}"
dry_run="$(normalize_boolean SYNTHETIC_RETENTION_DRY_RUN "${SYNTHETIC_RETENTION_DRY_RUN:-false}")"
ref_name="${REF_NAME:-main}"

validate_positive_integer "SYNTHETIC_RETENTION_DAYS" "${retention_days}"
if [ -z "${email_prefixes}" ]; then
  die "SYNTHETIC_RETENTION_EMAIL_PREFIXES must not be empty."
fi

log "Preparing synthetic retention in ${DEPLOY_PATH}"
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
if [ ! -f "scripts/synthetic_ops_retention.py" ]; then
  die "Retention script not found in repository checkout: scripts/synthetic_ops_retention.py"
fi
if ! docker compose -f "${compose_file}" exec -T app true >/dev/null 2>&1; then
  die "App container is not reachable via docker compose exec."
fi

dry_run_arg=""
if [ "${dry_run}" = "true" ]; then
  dry_run_arg="--dry-run"
fi

log "Running synthetic retention (ref=${ref_name}, days=${retention_days}, dry_run=${dry_run}, prefixes=${email_prefixes})"
docker compose -f "${compose_file}" exec -T app python - \
  --retention-days "${retention_days}" \
  --email-prefixes "${email_prefixes}" \
  ${dry_run_arg} \
  < scripts/synthetic_ops_retention.py

log "Synthetic retention finished successfully."
