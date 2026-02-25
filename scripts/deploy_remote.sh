#!/usr/bin/env bash
set -euo pipefail

if [ -z "${DEPLOY_PATH:-}" ] || [ -z "${REF_NAME:-}" ]; then
  echo "Missing required runtime variables."
  exit 1
fi

cd "${DEPLOY_PATH}"
if [ ! -d .git ]; then
  echo "Target path is not a git repository: ${DEPLOY_PATH}"
  exit 1
fi

compose_files=(-f docker-compose.prod.yml)
case "${PROFILE:-standard}" in
  standard)
    ;;
  proxy)
    compose_files+=( -f docker-compose.proxy.yml )
    ;;
  *)
    echo "Unsupported profile: ${PROFILE}"
    exit 1
    ;;
esac

run_compose() {
  docker compose "${compose_files[@]}" "$@"
}

PREV_SHA="$(git rev-parse HEAD)"
ROLLBACK_DONE="false"
rollback() {
  exit_code=$?
  if [ "${ROLLBACK_DONE}" = "true" ]; then
    exit "${exit_code}"
  fi
  ROLLBACK_DONE="true"

  echo "Deployment failed. Rolling back to ${PREV_SHA}..."
  git checkout "${PREV_SHA}" || true
  run_compose up --build -d || true
  docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head || true
  exit "${exit_code}"
}
trap rollback ERR

git fetch origin --tags
git checkout "${REF_NAME}"
if git show-ref --verify --quiet "refs/heads/${REF_NAME}"; then
  git pull --ff-only origin "${REF_NAME}"
fi

if [ "${RUN_BACKUP:-true}" = "true" ]; then
  mkdir -p backups
  ts="$(date +%Y%m%d-%H%M%S)"
  if docker compose -f docker-compose.prod.yml exec -T db true > /dev/null 2>&1; then
    docker compose -f docker-compose.prod.yml exec -T db sh -c \
      'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
      > "backups/predeploy-${ts}.sql"
  else
    echo "Skipping pre-deploy backup: db container is not running yet."
  fi
fi

run_compose up --build -d
docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head

if [ "${RUN_SMOKE:-true}" = "true" ]; then
  if [ -f scripts/deploy_smoke_check.py ]; then
    docker compose -f docker-compose.prod.yml exec -T app python scripts/deploy_smoke_check.py
  else
    echo "Missing scripts/deploy_smoke_check.py in deployed ref. Running fallback smoke checks."
    docker compose -f docker-compose.prod.yml exec -T app python - <<'PY'
import json
import urllib.error
import urllib.request
from uuid import uuid4

BASE_URL = "http://localhost:8000"


def request(path: str, *, method: str = "GET", body: dict | None = None, headers: dict | None = None, expected: int = 200):
    payload = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=payload, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.getcode()
            content = resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{method} {path} -> {exc.code}: {exc.read().decode('utf-8', errors='ignore')}") from exc
    if status != expected:
        raise RuntimeError(f"{method} {path} -> {status}, expected {expected}")
    return content

for endpoint in [
    "/health",
    "/ready",
    "/docs",
    "/metrics",
    "/portal",
    "/portal/static/app.js",
    "/portal/static/styles.css",
]:
    request(endpoint, expected=200)

suffix = uuid4().hex[:10]
email = f"deploy-smoke-{suffix}@guitaronline.dev"
password = "StrongPass123!"
request(
    "/api/v1/identity/auth/register",
    method="POST",
    body={"email": email, "password": password, "timezone": "UTC", "role": "student"},
    expected=201,
)
login_payload = json.loads(
    request(
        "/api/v1/identity/auth/login",
        method="POST",
        body={"email": email, "password": password},
        expected=200,
    ).decode("utf-8")
)
request(
    "/api/v1/identity/users/me",
    headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    expected=200,
)
print("Smoke checks passed.")
PY
  fi
fi

trap - ERR
echo "Deployment completed successfully."
