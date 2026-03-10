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
