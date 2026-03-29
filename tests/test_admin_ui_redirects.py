from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main_module


def test_admin_login_redirects_are_canonical() -> None:
    client = TestClient(main_module.app)

    for path in ("/login", "/login/", "/admin", "/admin/"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 308
        assert response.headers.get("location") == "/admin/login"
