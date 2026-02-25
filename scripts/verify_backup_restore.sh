#!/usr/bin/env bash
set -euo pipefail

compose_file="${COMPOSE_FILE:-docker-compose.prod.yml}"
backup_file="${1:-}"
timestamp="$(date +%Y%m%d-%H%M%S)"

if [ -z "${backup_file}" ]; then
  backup_file="backups/verify-${timestamp}.sql"
fi

mkdir -p "$(dirname "${backup_file}")"

if ! docker compose -f "${compose_file}" exec -T db true >/dev/null 2>&1; then
  echo "db container is not running for compose file: ${compose_file}" >&2
  exit 1
fi

if [ ! -f "${backup_file}" ]; then
  echo "Creating backup artifact: ${backup_file}"
  docker compose -f "${compose_file}" exec -T db sh -c \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
    > "${backup_file}"
else
  echo "Using existing backup artifact: ${backup_file}"
fi

verify_db="restore_verify_${timestamp}"
cleanup() {
  docker compose -f "${compose_file}" exec -T db sh -c \
    "psql -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" -d postgres -c \"DROP DATABASE IF EXISTS \\\"${verify_db}\\\";\"" \
    >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker compose -f "${compose_file}" exec -T db sh -c \
  "psql -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" -d postgres -c \"CREATE DATABASE \\\"${verify_db}\\\";\""

cat "${backup_file}" | docker compose -f "${compose_file}" exec -T db sh -c \
  "psql -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" -d \"${verify_db}\""

table_count="$(
  docker compose -f "${compose_file}" exec -T db sh -c \
    "psql -t -A -U \"\$POSTGRES_USER\" -d \"${verify_db}\" -c \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';\"" \
    | tr -d '\r\n'
)"

if [ -z "${table_count}" ] || [ "${table_count}" -le 0 ]; then
  echo "Restore verification failed: public schema has no tables in ${verify_db}" >&2
  exit 1
fi

echo "Backup/restore verification passed."
echo "  backup_file=${backup_file}"
echo "  verification_db=${verify_db}"
echo "  public_table_count=${table_count}"
