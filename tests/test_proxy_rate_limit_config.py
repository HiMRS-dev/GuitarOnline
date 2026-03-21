from __future__ import annotations

from pathlib import Path


def test_nginx_overwrites_forwarded_for_header_to_prevent_spoofing() -> None:
    config = Path("ops/nginx/default.conf").read_text(encoding="utf-8")
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in config
    assert "$proxy_add_x_forwarded_for" not in config


def test_nginx_enforces_https_redirect_and_hsts() -> None:
    config = Path("ops/nginx/default.conf").read_text(encoding="utf-8")
    assert "return 308 https://$host$request_uri;" in config
    assert "listen 443 ssl;" in config
    assert (
        'add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;'
        in config
    )


def test_proxy_profile_closes_internal_service_ports_and_exposes_tls() -> None:
    proxy_compose = Path("docker-compose.proxy.yml").read_text(encoding="utf-8")
    assert "app:\n    ports: []" in proxy_compose
    assert "prometheus:\n    ports: []" in proxy_compose
    assert "alertmanager:\n    ports: []" in proxy_compose
    assert "grafana:\n    ports: []" in proxy_compose
    assert "${PROXY_TLS_PUBLIC_PORT:-8443}:443" in proxy_compose
    assert "${PROXY_TLS_CERTS_PATH:-./ops/nginx/certs}:/etc/nginx/certs:ro" in proxy_compose


def test_nginx_healthchecks_pin_ipv4_loopback_instead_of_localhost() -> None:
    prod_compose = Path("docker-compose.prod.yml").read_text(encoding="utf-8")
    proxy_compose = Path("docker-compose.proxy.yml").read_text(encoding="utf-8")

    assert "http://127.0.0.1/" in prod_compose
    assert "http://localhost/" not in prod_compose
    assert "https://127.0.0.1/health" in proxy_compose
    assert "https://localhost/health" not in proxy_compose


def test_grafana_credentials_require_explicit_env_values() -> None:
    prod_compose = Path("docker-compose.prod.yml").read_text(encoding="utf-8")
    assert (
        "GF_SECURITY_ADMIN_USER: ${GRAFANA_ADMIN_USER:?GRAFANA_ADMIN_USER must be set}"
        in prod_compose
    )
    assert (
        "GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:?GRAFANA_ADMIN_PASSWORD must be set}"
        in prod_compose
    )


def test_deploy_script_fails_closed_on_missing_grafana_credentials() -> None:
    deploy_script = Path("scripts/deploy_remote.sh").read_text(encoding="utf-8")

    assert "validate_grafana_admin_env()" in deploy_script
    assert "Set both GRAFANA_ADMIN_USER and GRAFANA_ADMIN_PASSWORD." in deploy_script
    assert "append_env_override" not in deploy_script
    assert "JWT_SECRET" not in deploy_script
    assert "SECRET_KEY" not in deploy_script


def test_test_compose_stack_is_isolated_from_live_defaults() -> None:
    test_compose = Path("docker-compose.test.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "name: guitaronline-test" in test_compose
    assert 'APP_ENV: ${TEST_APP_ENV:-test}' in test_compose
    assert "${TEST_APP_HOST_PORT:-18000}:8000" in test_compose
    assert "${TEST_POSTGRES_HOST_PORT:-15432}:5432" in test_compose
    assert "${TEST_REDIS_HOST_PORT:-16379}:6379" in test_compose
    assert "guitaronline_test" in test_compose
    assert "auth_rate_limit_test" in test_compose
    assert (
        "BOOTSTRAP_ADMIN_EMAIL: ${TEST_BOOTSTRAP_ADMIN_EMAIL:-bootstrap-admin@guitaronline.dev}"
        in test_compose
    )
    assert (
        "AUTH_RATE_LIMIT_REGISTER_REQUESTS: ${TEST_AUTH_RATE_LIMIT_REGISTER_REQUESTS:-200}"
        in test_compose
    )
    assert (
        "AUTH_RATE_LIMIT_LOGIN_REQUESTS: ${TEST_AUTH_RATE_LIMIT_LOGIN_REQUESTS:-200}"
        in test_compose
    )
    assert (
        "AUTH_RATE_LIMIT_REFRESH_REQUESTS: ${TEST_AUTH_RATE_LIMIT_REFRESH_REQUESTS:-400}"
        in test_compose
    )
    assert "TEST_AUTH_RATE_LIMIT_REGISTER_REQUESTS=200" in env_example
    assert "TEST_AUTH_RATE_LIMIT_LOGIN_REQUESTS=200" in env_example
    assert "TEST_AUTH_RATE_LIMIT_REFRESH_REQUESTS=400" in env_example


def test_bootstrap_admin_script_requires_env_and_blocks_production_by_default() -> None:
    bootstrap_script = Path("scripts/bootstrap_admin.py").read_text(encoding="utf-8")

    assert "BOOTSTRAP_ADMIN_EMAIL" in bootstrap_script
    assert "BOOTSTRAP_ADMIN_PASSWORD" in bootstrap_script
    assert "Refusing to bootstrap admin in production." in bootstrap_script


def test_test_smoke_pool_reset_assets_are_declared_and_fail_closed() -> None:
    env_example = Path(".env.example").read_text(encoding="utf-8")
    smoke_pool_script = Path("scripts/reset_test_smoke_pool.py").read_text(encoding="utf-8")

    assert "TEST_SMOKE_ADMIN_EMAIL=smoke-admin-1@guitaronline.dev" in env_example
    assert "TEST_SMOKE_TEACHER_EMAIL=smoke-teacher-1@guitaronline.dev" in env_example
    assert "TEST_SMOKE_STUDENT_EMAIL=smoke-student-1@guitaronline.dev" in env_example
    assert "TEST_SMOKE_STUDENT_TWO_EMAIL=smoke-student-2@guitaronline.dev" in env_example
    assert "TEST_SMOKE_POOL_PASSWORD=StrongPass123!" in env_example
    assert "smoke-admin-1@guitaronline.dev" in smoke_pool_script
    assert "smoke-teacher-1@guitaronline.dev" in smoke_pool_script
    assert "smoke-student-1@guitaronline.dev" in smoke_pool_script
    assert "smoke-student-2@guitaronline.dev" in smoke_pool_script
    assert "Refusing to reset smoke pool outside APP_ENV=test." in smoke_pool_script
    assert "--allow-non-test" in smoke_pool_script


def test_perf_and_load_scripts_fail_closed_outside_test_by_default() -> None:
    perf_baseline_script = Path("scripts/admin_perf_baseline.py").read_text(encoding="utf-8")
    perf_probe_script = Path("scripts/admin_perf_probe.py").read_text(encoding="utf-8")
    load_sanity_script = Path("scripts/load_sanity.py").read_text(encoding="utf-8")

    assert "Refusing to run admin perf baseline outside APP_ENV=test" in perf_baseline_script
    assert "Refusing to run admin perf probe outside APP_ENV=test" in perf_probe_script
    assert "Refusing to run load sanity outside APP_ENV=test" in load_sanity_script
    assert "--allow-non-test" in perf_baseline_script
    assert "--allow-non-test" in perf_probe_script


def test_synthetic_ops_remote_runner_supports_test_contour_smoke_pool() -> None:
    runner_script = Path("scripts/run_synthetic_ops_remote.sh").read_text(encoding="utf-8")

    assert 'SYNTHETIC_OPS_CONTOUR:-live' in runner_script
    assert 'resolve_alert_on_failure()' in runner_script
    assert 'SYNTHETIC_OPS_ALERT_ON_FAILURE:-auto' in runner_script
    assert 'must be auto, true or false' in runner_script
    assert 'SYNTHETIC_OPS_AUTO_START_TEST_STACK' in runner_script
    assert 'compose_file="${COMPOSE_FILE:-docker-compose.test.yml}"' in runner_script
    assert (
        'admin_email="${SYNTHETIC_OPS_ADMIN_EMAIL:-smoke-admin-1@guitaronline.dev}"'
        in runner_script
    )
    assert (
        'teacher_email="${SYNTHETIC_OPS_TEACHER_EMAIL:-smoke-teacher-1@guitaronline.dev}"'
        in runner_script
    )
    assert (
        'student_email="${SYNTHETIC_OPS_STUDENT_EMAIL:-smoke-student-1@guitaronline.dev}"'
        in runner_script
    )
    assert 'scripts/reset_test_smoke_pool.py' in runner_script
    assert 'log "Resetting reusable smoke pool in test contour"' in runner_script
    assert 'python - < scripts/reset_test_smoke_pool.py' in runner_script
    assert (
        'log "Test contour app container is not reachable; starting app service"'
        in runner_script
    )
    assert 'log "Refreshing test contour app service from current checkout"' in runner_script
    assert "up -d --build --force-recreate app" in runner_script
    assert 'log "Applying test contour database migrations"' in runner_script
    assert "alembic upgrade head" in runner_script


def test_synthetic_ops_check_uses_existing_elevated_accounts_and_registers_student_without_role(
) -> None:
    synthetic_script = Path("scripts/synthetic_ops_check.py").read_text(encoding="utf-8")

    assert "Expected pre-provisioned {role} account for synthetic ops check" in synthetic_script
    assert '"role": role' not in synthetic_script
    assert '"/api/v1/identity/auth/register"' in synthetic_script


def test_synthetic_ops_workflow_supports_manual_test_contour() -> None:
    workflow = Path(".github/workflows/synthetic-ops-check.yml").read_text(encoding="utf-8")

    assert "contour:" in workflow
    assert 'default: "live"' in workflow
    assert "type: choice" in workflow
    assert "- test" in workflow
    assert "SYNTHETIC_OPS_CONTOUR" in workflow


def test_synthetic_ops_workflow_uses_auto_alert_policy_for_manual_runs() -> None:
    workflow = Path(".github/workflows/synthetic-ops-check.yml").read_text(encoding="utf-8")

    assert "alert_on_failure:" in workflow
    assert 'default: "auto"' in workflow
    assert "- auto" in workflow
    assert "- true" in workflow
    assert "- false" in workflow
    assert "Alert policy:" in workflow
    assert "github.event.inputs.alert_on_failure || 'auto'" in workflow


def test_ci_integration_api_uses_test_auth_rate_limits() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "AUTH_RATE_LIMIT_REGISTER_REQUESTS: 200" in workflow
    assert "AUTH_RATE_LIMIT_LOGIN_REQUESTS: 200" in workflow
    assert "AUTH_RATE_LIMIT_REFRESH_REQUESTS: 400" in workflow
