from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastapi.responses import FileResponse

import app.main as main_module


@pytest.mark.asyncio
async def test_portal_page_serves_frontend_index_file() -> None:
    response = await main_module.portal_page()

    assert isinstance(response, FileResponse)
    assert Path(response.path).name == "index.html"
    assert Path(response.path).exists()


def test_portal_static_styles_route_serves_css() -> None:
    client = TestClient(main_module.app)

    response = client.get("/portal/static/styles.css")

    assert response.status_code == 200
    assert "text/css" in response.headers.get("content-type", "")
    assert ":root {" in response.text


def test_portal_static_app_route_serves_javascript() -> None:
    client = TestClient(main_module.app)

    response = client.get("/portal/static/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "")
    assert 'const API_PREFIX = "/api/v1";' in response.text
