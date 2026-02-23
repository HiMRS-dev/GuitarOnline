from __future__ import annotations

import pytest

import app.main as main_module


@pytest.mark.asyncio
async def test_landing_page_contains_navigation_links() -> None:
    response = await main_module.landing_page()
    payload = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "GuitarOnline API" in payload
    assert 'href="/docs"' in payload
    assert 'href="/health"' in payload
    assert 'href="/ready"' in payload
    assert 'href="/metrics"' in payload
