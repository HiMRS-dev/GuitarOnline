from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main_module


def test_admin_login_redirects_are_canonical() -> None:
    client = TestClient(main_module.app)

    for path in ("/login", "/login/", "/admin", "/admin/"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 308
        assert response.headers.get("location") == "/admin/login"


def test_admin_login_route_redirects_to_shared_portal_auth() -> None:
    client = TestClient(main_module.app)

    for path in ("/admin/login", "/admin/login/"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 307
        assert (
            response.headers.get("location")
            == "/portal?auth=login&next=/admin/platform&entry=admin"
        )


def test_internal_admin_redirects_to_internal_login_without_session() -> None:
    client = TestClient(main_module.app)

    response = client.get("/internal-admin/", follow_redirects=False)

    assert response.status_code in (302, 303, 307)
    location = response.headers.get("location")
    assert location is not None
    assert location.endswith("/internal-admin/login")
