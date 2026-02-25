#!/usr/bin/env bash
set -euo pipefail

if [ -z "${DEPLOY_PATH:-}" ] || [ -z "${REF_NAME:-}" ]; then
  echo "DEPLOY_PATH and REF_NAME are required." >&2
  exit 1
fi

if [ -z "${KEEP_BACKUP:-}" ]; then
  KEEP_BACKUP="true"
fi

cd "${DEPLOY_PATH}"
if [ ! -d .git ]; then
  echo "Target path is not a git repository: ${DEPLOY_PATH}" >&2
  exit 1
fi

git fetch origin --tags
git checkout "${REF_NAME}"
if git show-ref --verify --quiet "refs/heads/${REF_NAME}"; then
  git pull --ff-only origin "${REF_NAME}"
fi

if [ ! -f scripts/verify_backup_restore.sh ]; then
  echo "Missing scripts/verify_backup_restore.sh in ref ${REF_NAME}" >&2
  exit 1
fi

timestamp="$(date +%Y%m%d-%H%M%S)"
backup_file="backups/verify-${timestamp}.sql"

bash scripts/verify_backup_restore.sh "${backup_file}"

if [ "${KEEP_BACKUP}" != "true" ]; then
  rm -f "${backup_file}"
  echo "Removed verification backup artifact: ${backup_file}"
fi
