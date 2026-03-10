from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main_module


def test_security_headers_are_present_on_health_endpoint() -> None:
    client = TestClient(main_module.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("permissions-policy") == "camera=(), microphone=(), geolocation=()"
    csp = response.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_swagger_docs_skip_csp_to_keep_ui_assets_working() -> None:
    client = TestClient(main_module.app)

    response = client.get("/docs")

    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert "content-security-policy" not in response.headers
