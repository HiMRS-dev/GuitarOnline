#!/usr/bin/env bash
set -euo pipefail

if [ -z "${DEPLOY_PATH:-}" ] || [ -z "${REF_NAME:-}" ]; then
  echo "DEPLOY_PATH and REF_NAME are required." >&2
  exit 1
fi

timestamp_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log() {
  printf '[backup-verify][%s] %s\n' "$(timestamp_utc)" "$*"
}

die() {
  printf '[backup-verify][%s][error] %s\n' "$(timestamp_utc)" "$*" >&2
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

  die "Unable to resolve verification ref: ${REF_NAME}"
}

if [ -z "${KEEP_BACKUP:-}" ]; then
  KEEP_BACKUP="true"
fi

log "=== Stage 1/3: Preflight ==="
require_command git
require_command docker
if ! docker compose version >/dev/null 2>&1; then
  die "docker compose plugin is not available for user $(id -un)"
fi

log "Preparing verification path ${DEPLOY_PATH}"
ensure_repo_checkout
cd "${DEPLOY_PATH}"
log "Verification user: $(id -un)"
log "Origin URL: $(git remote get-url origin 2>/dev/null || echo '<unset>')"
log "Requested ref: ${REF_NAME}"
if [ ! -f "${DEPLOY_PATH}/.env" ]; then
  die "Missing ${DEPLOY_PATH}/.env. Run deploy workflow first so environment is provisioned."
fi
log ".env file detected."

log "=== Stage 2/3: Git sync ==="
sync_ref
log "Checked out SHA: $(git rev-parse HEAD)"

if [ ! -f scripts/verify_backup_restore.sh ]; then
  die "Missing scripts/verify_backup_restore.sh in ref ${REF_NAME}"
fi

timestamp="$(date +%Y%m%d-%H%M%S)"
backup_file="backups/verify-${timestamp}.sql"

log "=== Stage 3/3: Backup/restore verification ==="
log "Running backup/restore verification script"
bash scripts/verify_backup_restore.sh "${backup_file}"

if [ "${KEEP_BACKUP}" != "true" ]; then
  rm -f "${backup_file}"
  log "Removed verification backup artifact: ${backup_file}"
fi
