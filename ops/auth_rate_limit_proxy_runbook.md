# Auth Rate-Limit Proxy Runbook

This runbook defines production-safe configuration and validation for identity rate-limiting
when GuitarOnline runs behind reverse proxy profile (`docker-compose.proxy.yml`).

## 1) Scope and Trust Model

- Identity endpoints are rate-limited by resolved client IP:
  - `POST /api/v1/identity/auth/register`
  - `POST /api/v1/identity/auth/login`
  - `POST /api/v1/identity/auth/refresh`
- Application uses `X-Forwarded-For` only when request source IP belongs to
  `AUTH_RATE_LIMIT_TRUSTED_PROXY_IPS`.
- Trust boundary requirement:
  - only immediate proxy network(s) may be listed in `AUTH_RATE_LIMIT_TRUSTED_PROXY_IPS`,
  - never add public internet CIDRs or arbitrary client subnets.

## 2) Required Production Configuration

1. Redis-backed limiter:
   - `AUTH_RATE_LIMIT_BACKEND=redis`
   - `REDIS_URL=redis://redis:6379/0` (or production equivalent)
   - `AUTH_RATE_LIMIT_REDIS_NAMESPACE=auth_rate_limit` (or approved namespace)
2. Trusted proxy source list:
   - default proxy profile value:
     - `AUTH_RATE_LIMIT_TRUSTED_PROXY_IPS=127.0.0.1,::1,172.16.0.0/12`
   - include only addresses/CIDRs that can directly reach app container.
3. Proxy header hygiene:
   - Nginx must overwrite `X-Forwarded-For` with immediate remote client IP
     (no pass-through of user-supplied header chain).
4. Ingress TLS/HSTS policy:
   - reverse proxy must terminate TLS on `443`,
   - HTTP `80` must only redirect to HTTPS,
   - HSTS header must be enabled on TLS responses.
5. Exposure constraint:
   - in proxy profile, app service must not publish `8000` externally (`ports: []` override),
   - monitoring ports (`9090`, `9093`, `3000`) must stay internal-only.
6. Proxy TLS assets:
   - default cert path: `ops/nginx/certs/tls.crt` and `ops/nginx/certs/tls.key`,
   - override via `.env`: `PROXY_TLS_CERTS_PATH`,
   - production deploy preflight blocks proxy deploy when files are missing.

## 3) Pre-Deploy Checks

1. Verify compose-merged env:
   - `docker compose -f docker-compose.prod.yml -f docker-compose.proxy.yml config | grep -E "AUTH_RATE_LIMIT_(BACKEND|TRUSTED_PROXY_IPS)|REDIS_URL"`
2. Verify proxy profile removes direct app/monitoring host ports:
   - `docker compose -f docker-compose.prod.yml -f docker-compose.proxy.yml config | grep -n "ports:" -A 4`
3. Verify TLS cert assets are present on target host:
   - `${PROXY_TLS_CERTS_PATH:-./ops/nginx/certs}/tls.crt`
   - `${PROXY_TLS_CERTS_PATH:-./ops/nginx/certs}/tls.key`
4. Verify Redis is reachable:
   - `docker compose -f docker-compose.prod.yml exec -T redis redis-cli ping`
   - expected: `PONG`

## 4) Runtime Validation Checklist

Use a temporary low threshold for deterministic verification in non-production or short maintenance
window:

- `AUTH_RATE_LIMIT_WINDOW_SECONDS=60`
- `AUTH_RATE_LIMIT_LOGIN_REQUESTS=2`

Then validate through proxy public TLS URL (`https://localhost:${PROXY_TLS_PUBLIC_PORT:-8443}`):

1. Baseline limiter trigger:
   - execute 3 login attempts with invalid credentials from same client.
   - expected:
     - first 2 responses: `401` (invalid credentials),
     - third response: `429` (rate-limited).
2. Header spoof resistance:
   - repeat requests with custom `X-Forwarded-For` values from same external client.
   - expected:
     - limiter behavior remains consistent with proxy-resolved identity policy,
     - no unlimited bypass by arbitrary header injection.
3. App readiness and probe path behind proxy:
   - `curl -k -fsS https://localhost:${PROXY_TLS_PUBLIC_PORT:-8443}/health`
   - expected: `{"status":"ok"}`.
4. Security regression suite:
   - `py -m poetry run pytest -q tests/test_identity_rate_limit.py tests/test_config_security.py tests/test_security_surface.py tests/test_pii_field_visibility.py`

## 5) Failure Modes and Remediation

1. Symptom: all clients share one limiter bucket.
   - likely cause: trusted proxy list missing runtime proxy source.
   - action: correct `AUTH_RATE_LIMIT_TRUSTED_PROXY_IPS` to immediate proxy CIDR/IP.
2. Symptom: easy rate-limit bypass by rotating `X-Forwarded-For`.
   - likely cause: proxy passes through user-provided `X-Forwarded-For`.
   - action: enforce proxy overwrite policy for `X-Forwarded-For` and redeploy proxy config.
3. Symptom: limiter ineffective across replicas.
   - likely cause: `AUTH_RATE_LIMIT_BACKEND=memory` in distributed runtime.
   - action: switch to `redis`, ensure `REDIS_URL` is valid, redeploy.

## 6) Change Control Notes

- Any update to `AUTH_RATE_LIMIT_TRUSTED_PROXY_IPS` must include:
  - explicit rationale,
  - validated source IP/CIDR inventory,
  - post-change checklist evidence (section 4).
- Keep this runbook linked from:
  - `ops/release_checklist.md`
  - `ops/production_hardening_checklist.md`
