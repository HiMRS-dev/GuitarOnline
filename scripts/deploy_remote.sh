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
        result = value
      }
      END {
        if (result != "") {
          print result
        }
      }
    ' "${env_file}"
  )"
  sanitize_env_value "${raw_value}"
}

validate_auth_rate_limiter_env() {
  local backend
  local redis_url

  backend="$(read_env_value "AUTH_RATE_LIMIT_BACKEND")"
  if [ -z "${backend}" ]; then
    backend="redis"
  fi
  backend="$(printf '%s' "${backend}" | tr '[:upper:]' '[:lower:]')"
  if [ "${backend}" != "redis" ]; then
    die "AUTH_RATE_LIMIT_BACKEND must resolve to redis for deploy pipeline. Got: ${backend}"
  fi

  redis_url="$(read_env_value "REDIS_URL")"
  if [ -z "${redis_url}" ]; then
    redis_url="redis://redis:6379/0"
    log "Auth rate-limiter preflight: AUTH_RATE_LIMIT_BACKEND=redis, REDIS_URL fallback will be used (${redis_url})."
    return
  fi
  log "Auth rate-limiter preflight: AUTH_RATE_LIMIT_BACKEND=redis, REDIS_URL is set."
}

validate_grafana_admin_env() {
  local admin_user
  local admin_password

  admin_user="$(read_env_value "GRAFANA_ADMIN_USER")"
  admin_password="$(read_env_value "GRAFANA_ADMIN_PASSWORD")"

  if [ -z "${admin_user}" ] || [ -z "${admin_password}" ]; then
    die "Missing required Grafana admin env in ${DEPLOY_PATH}/.env. Set both GRAFANA_ADMIN_USER and GRAFANA_ADMIN_PASSWORD."
  fi

  log "Grafana admin credentials preflight: required values are present."
}

resolve_deploy_path() {
  local raw_path="$1"

  if [[ "${raw_path}" = /* ]]; then
    printf '%s' "${raw_path}"
    return
  fi

  printf '%s/%s' "${DEPLOY_PATH}" "${raw_path#./}"
}

validate_proxy_tls_assets() {
  if [ "${PROFILE:-standard}" != "proxy" ]; then
    return
  fi

  local certs_dir
  local cert_file
  local key_file
  certs_dir="$(read_env_value "PROXY_TLS_CERTS_PATH")"
  if [ -z "${certs_dir}" ]; then
    certs_dir="./ops/nginx/certs"
  fi
  certs_dir="$(resolve_deploy_path "${certs_dir}")"
  cert_file="${certs_dir}/tls.crt"
  key_file="${certs_dir}/tls.key"

  if [ ! -f "${cert_file}" ] || [ ! -f "${key_file}" ]; then
    die "Proxy TLS assets are required for PROFILE=proxy. Expected files: ${cert_file}, ${key_file}"
  fi

  log "Proxy TLS preflight: certificate assets found in ${certs_dir}."
}

available_kb() {
  local path="$1"
  df -Pk "${path}" | awk 'NR==2 {print $4}'
}

prune_old_predeploy_backups() {
  local backups_dir="${DEPLOY_PATH}/backups"
  local keep="${PREDEPLOY_BACKUP_KEEP_COUNT:-5}"
  local total=0
  local removed=0
  local i=0

  if [ ! -d "${backups_dir}" ]; then
    return
  fi

  mapfile -t predeploy_files < <(
    find "${backups_dir}" -maxdepth 1 -type f -name 'predeploy-*.sql' -printf '%f\n' | sort -r
  )
  total="${#predeploy_files[@]}"
  if [ "${total}" -le "${keep}" ]; then
    return
  fi

  for ((i=keep; i<total; i++)); do
    rm -f "${backups_dir}/${predeploy_files[${i}]}" || true
    removed=$((removed + 1))
  done

  log "Pruned old pre-deploy backups: removed=${removed}, kept=${keep}."
}

reclaim_disk_if_low() {
  local phase="$1"
  local min_free_kb="${DEPLOY_MIN_FREE_KB:-1048576}"
  local free_before=0
  local free_after=0

  free_before="$(available_kb "${DEPLOY_PATH}")"
  if [ -z "${free_before}" ]; then
    warn "Unable to determine free disk space during ${phase}."
    return
  fi

  log "Free disk before ${phase}: ${free_before}KB (threshold=${min_free_kb}KB)."
  if [ "${free_before}" -ge "${min_free_kb}" ]; then
    return
  fi

  warn "Low disk space detected during ${phase}. Starting safe cleanup."
  prune_old_predeploy_backups
  docker container prune -f >/dev/null 2>&1 || warn "docker container prune failed; continuing."
  docker image prune -af >/dev/null 2>&1 || warn "docker image prune failed; continuing."
  docker builder prune -af >/dev/null 2>&1 || warn "docker builder prune failed; continuing."

  free_after="$(available_kb "${DEPLOY_PATH}")"
  if [ -n "${free_after}" ]; then
    log "Free disk after ${phase} cleanup: ${free_after}KB."
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

TMPDIR="${DEPLOY_PATH}/.tmp/deploy"
mkdir -p "${TMPDIR}"
find "${TMPDIR}" -mindepth 1 -maxdepth 1 -type f -name '.tmp-compose-build-metadataFile-*' -delete 2>/dev/null || true
export TMPDIR
log "Using TMPDIR=${TMPDIR} for compose temporary files."

if [ ! -f "${DEPLOY_PATH}/.env" ]; then
  die "Missing ${DEPLOY_PATH}/.env. Ensure PROD_ENV_FILE_B64 is configured and upload step succeeded."
fi
log ".env file detected."
validate_auth_rate_limiter_env
validate_grafana_admin_env

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
validate_proxy_tls_assets

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
    docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head </dev/null || true
  else
    warn "Deployment failed during initial bootstrap and there is no previous SHA to roll back to."
  fi
  exit "${exit_code}"
}
trap rollback ERR

log "=== Stage 2/6: Git sync ==="
sync_ref
log "Checked out SHA: $(git rev-parse HEAD)"
reclaim_disk_if_low "pre-backup"

if [ "${RUN_BACKUP:-true}" = "true" ]; then
  log "=== Stage 3/6: Pre-deploy backup ==="
  log "Creating pre-deploy backup (if db container is running)"
  mkdir -p backups
  ts="$(date +%Y%m%d-%H%M%S)"
  if docker compose -f docker-compose.prod.yml exec -T db true </dev/null > /dev/null 2>&1; then
    docker compose -f docker-compose.prod.yml exec -T db sh -c \
      'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
      </dev/null > "backups/predeploy-${ts}.sql"
  else
    warn "Skipping pre-deploy backup: db container is not running yet."
  fi
else
  log "Skipping pre-deploy backup (RUN_BACKUP=${RUN_BACKUP})"
fi

log "=== Stage 4/6: Compose pull/build/up ==="
reclaim_disk_if_low "pre-build"
log "Pulling latest service images where available"
run_compose pull --ignore-pull-failures || true

log "Building and starting services"
run_compose up --build -d

log "=== Stage 5/6: Database migrations ==="
log "Running Alembic migrations"
docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head </dev/null

if [ "${RUN_SMOKE:-true}" = "true" ]; then
  log "=== Stage 6/6: Smoke checks ==="
  log "Waiting for app HTTP readiness before smoke checks"
  app_ready="false"
  for _ in $(seq 1 30); do
    if docker compose -f docker-compose.prod.yml exec -T app python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=5)" </dev/null > /dev/null 2>&1; then
      app_ready="true"
      break
    fi
    sleep 2
  done
  if [ "${app_ready}" != "true" ]; then
    die "App HTTP readiness check failed before smoke checks."
  fi

  log "Running smoke checks"
  if [ -f scripts/deploy_smoke_check.py ]; then
    smoke_log="$(mktemp)"
    if ! docker compose -f docker-compose.prod.yml exec -T app python scripts/deploy_smoke_check.py </dev/null | tee "${smoke_log}"; then
      rm -f "${smoke_log}"
      die "Smoke script failed before completion."
    fi
    if ! grep -Fq "Ops-only live smoke passed." "${smoke_log}" && ! grep -Fq "Role-based release gate passed." "${smoke_log}"; then
      rm -f "${smoke_log}"
      die "Smoke script output missing expected marker: Ops-only live smoke passed. or Role-based release gate passed."
    fi
    if ! grep -Fq "Smoke checks passed." "${smoke_log}"; then
      rm -f "${smoke_log}"
      die "Smoke script output missing marker: Smoke checks passed."
    fi
    rm -f "${smoke_log}"
    log "Smoke markers verified."
  else
    die "Missing scripts/deploy_smoke_check.py in deployed ref; role-based release gate is required."
  fi
else
  log "Skipping smoke checks (RUN_SMOKE=${RUN_SMOKE})"
fi

trap - ERR
log "Deployment completed successfully."
log "deployed_sha=$(git rev-parse HEAD)"
