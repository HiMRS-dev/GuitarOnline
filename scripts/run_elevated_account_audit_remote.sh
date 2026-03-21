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
  printf '[elevated-audit][%s] %s\n' "$(timestamp_utc)" "$*"
}

die() {
  printf '[elevated-audit][%s][error] %s\n' "$(timestamp_utc)" "$*" >&2
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

compose_file="${COMPOSE_FILE:-docker-compose.prod.yml}"
ref_name="${REF_NAME:-main}"
container_output_dir="${ELEVATED_ACCOUNT_AUDIT_CONTAINER_OUTPUT_DIR:-/tmp/elevated-account-audit}"
host_output_dir_input="${ELEVATED_ACCOUNT_AUDIT_OUTPUT_DIR:-backups/reports/elevated-account-audit}"
host_output_dir="$(resolve_path "${host_output_dir_input}")"

log "Preparing elevated-account audit in ${DEPLOY_PATH}"
require_command docker
require_command git
require_command awk
require_command tr
require_command basename

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
if [ -f "scripts/user_origin_audit.py" ]; then
  audit_script_path="scripts/user_origin_audit.py"
elif [ -f "scripts/elevated_account_audit.py" ]; then
  audit_script_path="scripts/elevated_account_audit.py"
else
  die "Audit script not found in repository checkout."
fi
if ! docker compose -f "${compose_file}" exec -T app true </dev/null >/dev/null 2>&1; then
  die "App container is not reachable via docker compose exec."
fi

mkdir -p "${host_output_dir}"
audit_log="${host_output_dir}/elevated-account-audit-remote.log"
rm -f "${audit_log}"

log "Running elevated-account audit script in app container"
set +e
docker compose -f "${compose_file}" exec -T app python - \
  --output-dir "${container_output_dir}" \
  < "${audit_script_path}" 2>&1 | tee "${audit_log}"
audit_exit="${PIPESTATUS[0]}"
set -e
if [ "${audit_exit}" -ne 0 ]; then
  die "Audit command failed with exit code ${audit_exit}. See ${audit_log}"
fi

container_json_path="$(
  awk -F= '
    {
      marker = "elevated_account_audit_json="
      idx = index($0, marker)
      if (idx <= 0) {
        next
      }
      value = substr($0, idx + length(marker))
      print value
    }
  ' "${audit_log}" | tail -n 1 || true
)"
container_json_path="$(printf '%s' "${container_json_path}" | tr -d '\r')"
if [ -z "${container_json_path}" ]; then
  die "Failed to parse JSON report path from audit output."
fi

container_md_path="$(
  awk -F= '
    {
      marker = "elevated_account_audit_markdown="
      idx = index($0, marker)
      if (idx <= 0) {
        next
      }
      value = substr($0, idx + length(marker))
      print value
    }
  ' "${audit_log}" | tail -n 1 || true
)"
container_md_path="$(printf '%s' "${container_md_path}" | tr -d '\r')"
if [ -z "${container_md_path}" ]; then
  die "Failed to parse Markdown report path from audit output."
fi

host_json_path="${host_output_dir}/$(basename "${container_json_path}")"
host_md_path="${host_output_dir}/$(basename "${container_md_path}")"

log "Copying audit artifacts from container to host output directory"
docker compose -f "${compose_file}" cp "app:${container_json_path}" "${host_json_path}"
docker compose -f "${compose_file}" cp "app:${container_md_path}" "${host_md_path}"
chmod 600 "${host_json_path}" "${host_md_path}" || true

docker compose -f "${compose_file}" exec -T app sh -c \
  "rm -f \"${container_json_path}\" \"${container_md_path}\"" >/dev/null 2>&1 || true

log "Elevated-account audit completed."
echo "elevated_account_audit_host_json=${host_json_path}"
echo "elevated_account_audit_host_markdown=${host_md_path}"
echo "elevated_account_audit_status=success"
